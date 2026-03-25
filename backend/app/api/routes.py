"""API route definitions."""

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from app.models.models import Deployment, DeployedVM, DeploymentLog, StackDefinition, User
from app.schemas.schemas import (
    DeploymentDetailOut,
    DeploymentOut,
    DeployRequest,
    LoginRequest,
    LogEntry,
    StackListOut,
    StackOut,
    TokenResponse,
    VMOut,
)
from app.services.stack_loader import get_stack_by_slug, load_all_stacks, parse_stack
from app.services.proxmox_service import proxmox_service

# ---------------------------------------------------------------------------
# Router instances
# ---------------------------------------------------------------------------
auth_router = APIRouter(prefix="/auth", tags=["auth"])
stacks_router = APIRouter(prefix="/stacks", tags=["stacks"])
deploy_router = APIRouter(prefix="/deployments", tags=["deployments"])
infra_router = APIRouter(prefix="/infra", tags=["infrastructure"])


# ===========================================================================
# AUTH
# ===========================================================================
@auth_router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Identifiants incorrects")

    token = create_access_token({"sub": user.username, "role": user.role})
    return TokenResponse(
        access_token=token, username=user.username, role=user.role
    )


@auth_router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


# ===========================================================================
# STACKS
# ===========================================================================
@stacks_router.get("/", response_model=list[StackListOut])
async def list_stacks():
    """List all available stack definitions."""
    raw_stacks = load_all_stacks()
    result = []
    for data in raw_stacks:
        result.append(
            StackListOut(
                id=data.get("slug", ""),
                slug=data.get("slug", ""),
                name=data["name"],
                description=data.get("description"),
                category=data.get("category", "other"),
                icon=data.get("icon", "server"),
                version=data.get("version", "1.0.0"),
                vm_count=len(data.get("vms", [])),
                service_count=len(data.get("services", [])),
            )
        )
    return result


@stacks_router.get("/{slug}", response_model=StackOut)
async def get_stack(slug: str):
    """Get detailed stack definition with services and VMs."""
    data = get_stack_by_slug(slug)
    if not data:
        raise HTTPException(status_code=404, detail="Stack introuvable")
    return parse_stack(data)


# ===========================================================================
# DEPLOYMENTS
# ===========================================================================
@deploy_router.post("/", response_model=DeploymentOut, status_code=201)
async def create_deployment(
    body: DeployRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create and launch a new stack deployment."""
    # Validate stack exists
    stack_data = get_stack_by_slug(body.stack_slug)
    if not stack_data:
        raise HTTPException(status_code=404, detail="Stack introuvable")

    # Get or create stack in DB
    result = await db.execute(
        select(StackDefinition).where(StackDefinition.slug == body.stack_slug)
    )
    stack_db = result.scalar_one_or_none()
    if not stack_db:
        stack_db = StackDefinition(
            slug=body.stack_slug,
            name=stack_data["name"],
            description=stack_data.get("description"),
            category=stack_data.get("category", "other"),
            yaml_path=stack_data.get("_file", ""),
        )
        db.add(stack_db)
        await db.flush()

    # Get user
    user_result = await db.execute(
        select(User).where(User.username == current_user["username"])
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    # Create deployment
    deployment = Deployment(
        name=body.name,
        stack_id=stack_db.id,
        user_id=user.id,
        selected_services=body.selected_services,
        vm_specs_override=body.vm_specs_override,
        network_config=body.network_config,
        status="pending",
    )
    db.add(deployment)
    await db.flush()

    # Launch Celery task
    from app.services.deployer import deploy_stack_task

    task = deploy_stack_task.delay(deployment.id)
    deployment.celery_task_id = task.id
    await db.flush()

    return DeploymentOut(
        id=deployment.id,
        name=deployment.name,
        stack_slug=body.stack_slug,
        stack_name=stack_data["name"],
        status=deployment.status,
        selected_services=deployment.selected_services,
        vm_count=len(stack_data.get("vms", [])),
        created_at=deployment.created_at,
        started_at=deployment.started_at,
        completed_at=deployment.completed_at,
        error_message=deployment.error_message,
    )


@deploy_router.get("/", response_model=list[DeploymentOut])
async def list_deployments(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all deployments for the current user."""
    result = await db.execute(
        select(Deployment)
        .options(selectinload(Deployment.stack), selectinload(Deployment.vms))
        .join(User)
        .where(User.username == current_user["username"])
        .order_by(Deployment.created_at.desc())
    )
    deployments = result.scalars().all()

    return [
        DeploymentOut(
            id=d.id,
            name=d.name,
            stack_slug=d.stack.slug if d.stack else "",
            stack_name=d.stack.name if d.stack else "",
            status=d.status,
            selected_services=d.selected_services or [],
            vm_count=len(d.vms) if d.vms is not None else 0,
            created_at=d.created_at,
            started_at=d.started_at,
            completed_at=d.completed_at,
            error_message=d.error_message,
        )
        for d in deployments
    ]


@deploy_router.get("/{deployment_id}", response_model=DeploymentDetailOut)
async def get_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get detailed deployment info including VMs."""
    result = await db.execute(
        select(Deployment)
        .options(selectinload(Deployment.vms), selectinload(Deployment.stack))
        .where(Deployment.id == deployment_id)
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Déploiement introuvable")

    return DeploymentDetailOut(
        id=deployment.id,
        name=deployment.name,
        stack_slug=deployment.stack.slug if deployment.stack else "",
        stack_name=deployment.stack.name if deployment.stack else "",
        status=deployment.status,
        selected_services=deployment.selected_services or [],
        vm_count=len(deployment.vms),
        created_at=deployment.created_at,
        started_at=deployment.started_at,
        completed_at=deployment.completed_at,
        error_message=deployment.error_message,
        vms=[
            VMOut(
                id=vm.id,
                vm_name=vm.vm_name,
                proxmox_vmid=vm.proxmox_vmid,
                ip_address=vm.ip_address,
                status=vm.status,
                roles=vm.roles or [],
                specs=vm.specs,
            )
            for vm in deployment.vms
        ],
    )


@deploy_router.get("/{deployment_id}/logs", response_model=list[LogEntry])
async def get_deployment_logs(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get deployment logs."""
    result = await db.execute(
        select(DeploymentLog)
        .where(DeploymentLog.deployment_id == deployment_id)
        .order_by(DeploymentLog.timestamp.asc())
    )
    return result.scalars().all()


@deploy_router.post("/{deployment_id}/stop")
async def stop_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Stop all VMs in a deployment."""
    result = await db.execute(
        select(Deployment)
        .options(selectinload(Deployment.vms))
        .where(Deployment.id == deployment_id)
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Déploiement introuvable")

    for vm in deployment.vms:
        if vm.proxmox_vmid:
            try:
                proxmox_service.stop_vm(vm.proxmox_vmid)
                vm.status = "stopped"
            except Exception as e:
                logger.warning(f"Failed to stop VM {vm.proxmox_vmid}: {e}")
                vm.status = "error"

    deployment.status = "stopped"
    await db.commit()
    return {"status": "stopped", "message": "VMs arrêtées"}


@deploy_router.delete("/{deployment_id}")
async def destroy_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Destroy all VMs and delete the deployment."""
    result = await db.execute(
        select(Deployment)
        .options(selectinload(Deployment.vms))
        .where(Deployment.id == deployment_id)
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="Déploiement introuvable")

    for vm in deployment.vms:
        if vm.proxmox_vmid:
            try:
                proxmox_service.destroy_vm(vm.proxmox_vmid)
            except Exception as e:
                logger.warning(f"Failed to destroy VM {vm.proxmox_vmid}: {e}")

    deployment.status = "destroyed"
    await db.commit()
    return {"status": "destroyed", "message": "Déploiement détruit"}


# ===========================================================================
# INFRASTRUCTURE
# ===========================================================================
@infra_router.get("/proxmox/status")
async def proxmox_status(current_user: dict = Depends(require_admin)):
    """Get Proxmox node health status (admin only)."""
    return proxmox_service.get_node_status()


@infra_router.get("/proxmox/templates")
async def proxmox_templates(current_user: dict = Depends(require_admin)):
    """List available VM templates (admin only)."""
    return proxmox_service.list_templates()


@infra_router.get("/ansible/roles")
async def ansible_roles(current_user: dict = Depends(require_admin)):
    """List available Ansible roles (admin only)."""
    from app.services.ansible_service import ansible_service
    return {"roles": ansible_service.list_available_roles()}
