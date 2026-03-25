"""Deployment orchestrator — Celery task that runs the full pipeline."""

import time
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.models.models import Deployment, DeployedVM, DeploymentLog, StackDefinition
from app.services.proxmox_service import proxmox_service
from app.services.ansible_service import ansible_service
from app.services.stack_loader import get_stack_by_slug, resolve_services_to_vms

settings = get_settings()

# Celery tasks use sync DB access (not async).
# Strip the async driver prefix so SQLAlchemy can use the sync driver.
_sync_url = settings.database_url
for _prefix, _replacement in (
    ("+aiosqlite", ""),
    ("+asyncpg", "+psycopg2"),
):
    _sync_url = _sync_url.replace(_prefix, _replacement)

sync_engine = create_engine(_sync_url)
SyncSession = sessionmaker(bind=sync_engine)


def _log(db: Session, deployment_id: str, message: str, level: str = "info", phase: str = None):
    """Write a log entry for a deployment."""
    entry = DeploymentLog(
        deployment_id=deployment_id,
        level=level,
        phase=phase,
        message=message,
    )
    db.add(entry)
    db.commit()
    logger.log(level.upper(), f"[{deployment_id[:8]}] {message}")


def _update_status(db: Session, deployment_id: str, status: str, error: str = None):
    """Update deployment status."""
    deploy = db.query(Deployment).get(deployment_id)
    if deploy:
        deploy.status = status
        if error:
            deploy.error_message = error
        # Set completed_at for all terminal states
        if status in ("running", "failed", "partial", "stopped", "destroyed"):
            deploy.completed_at = datetime.now(timezone.utc)
        db.commit()


def _topological_sort(vm_records: list) -> list:
    """
    Return vm_records sorted so that each VM comes after all its depends_on.
    Falls back to original order if a circular dependency is detected.
    """
    name_to_item = {vdef["name"]: (rec, vdef) for rec, vdef in vm_records}
    visited = set()
    result = []

    def visit(name: str, stack: set):
        if name in stack:
            logger.warning(f"Circular dependency detected at '{name}', skipping sort")
            return
        if name in visited:
            return
        stack.add(name)
        item = name_to_item.get(name)
        if item:
            _, vdef = item
            for dep in vdef.get("depends_on", []):
                visit(dep, stack)
        stack.discard(name)
        visited.add(name)
        if item:
            result.append(item)

    for _, vdef in vm_records:
        visit(vdef["name"], set())

    # Preserve any items not reached (safety net)
    seen_names = {vdef["name"] for _, vdef in result}
    for rec, vdef in vm_records:
        if vdef["name"] not in seen_names:
            result.append((rec, vdef))

    return result


def _wait_for_ip(
    db: Session,
    deployment_id: str,
    vm_record: DeployedVM,
    retry_count: int,
    retry_interval: int,
) -> bool:
    """
    Poll Proxmox guest agent until we get a non-loopback IPv4 address.
    Returns True if IP was found, False otherwise.
    """
    for attempt in range(1, retry_count + 1):
        try:
            agent_info = proxmox_service.node.qemu(
                vm_record.proxmox_vmid
            ).agent("network-get-interfaces").get()

            for iface in agent_info.get("result", []):
                for addr in iface.get("ip-addresses", []):
                    if (
                        addr.get("ip-address-type") == "ipv4"
                        and not addr["ip-address"].startswith("127.")
                        and not addr["ip-address"].startswith("169.254.")
                    ):
                        vm_record.ip_address = addr["ip-address"]
                        db.commit()
                        _log(
                            db, deployment_id,
                            f"IP récupérée pour {vm_record.vm_name}: {vm_record.ip_address}",
                            phase="configuring",
                        )
                        return True
        except Exception as exc:
            logger.debug(f"IP attempt {attempt}/{retry_count} for {vm_record.vm_name}: {exc}")

        if attempt < retry_count:
            _log(
                db, deployment_id,
                f"En attente de l'IP de {vm_record.vm_name} "
                f"(tentative {attempt}/{retry_count})...",
                phase="configuring",
            )
            time.sleep(retry_interval)

    _log(
        db, deployment_id,
        f"Impossible de récupérer l'IP de {vm_record.vm_name} après {retry_count} tentatives",
        level="warn",
        phase="configuring",
    )
    return False


@celery_app.task(bind=True, name="deploy_stack")
def deploy_stack_task(self, deployment_id: str):
    """
    Main deployment pipeline:
    1. Load stack definition
    2. Resolve services → VMs
    3. Clone templates on Proxmox
    4. Configure VMs (specs, network)
    5. Start VMs
    6. Wait for VMs to boot + get IPs
    7. Run Ansible roles on each VM (respecting dependencies)
    8. Mark deployment as running
    """
    db = SyncSession()

    try:
        deployment = db.query(Deployment).get(deployment_id)
        if not deployment:
            logger.error(f"Deployment {deployment_id} not found")
            return {"status": "error", "message": "Deployment not found"}

        deployment.status = "provisioning"
        deployment.started_at = datetime.now(timezone.utc)
        db.commit()

        _log(db, deployment_id, "Démarrage du déploiement", phase="init")

        # ── Step 1: Load stack ──
        stack_def = db.query(StackDefinition).get(deployment.stack_id)
        stack_data = get_stack_by_slug(stack_def.slug if stack_def else "")
        if not stack_data:
            raise Exception(
                f"Stack definition not found: {stack_def.slug if stack_def else 'unknown'}"
            )

        _log(db, deployment_id, f"Stack chargée: {stack_data['name']}", phase="init")

        # ── Step 2: Resolve VMs ──
        needed_vms = resolve_services_to_vms(stack_data, deployment.selected_services)
        _log(
            db, deployment_id,
            f"{len(needed_vms)} VM(s) à provisionner",
            phase="provisioning",
        )

        # ── Step 3 & 4: Validate templates, clone and configure each VM ──
        # Pre-validate all templates before starting to avoid partial deployments
        for vm_def in needed_vms:
            tpl = proxmox_service.find_template_vmid(vm_def["template"])
            if tpl is None:
                raise Exception(
                    f"Template '{vm_def['template']}' introuvable sur Proxmox. "
                    f"Créez le template avant de lancer le déploiement."
                )

        # Validate all roles exist before starting
        missing_roles = []
        for vm_def in needed_vms:
            for role in vm_def.get("roles", []):
                if not ansible_service.check_role_exists(role):
                    missing_roles.append(role)
        if missing_roles:
            raise Exception(
                f"Rôles Ansible manquants : {', '.join(sorted(set(missing_roles)))}"
            )

        vm_records = []
        for vm_def in needed_vms:
            vm_name = f"{deployment.name}-{vm_def['name']}".lower().replace(" ", "-")

            _log(db, deployment_id, f"Clonage de {vm_name}...", phase="provisioning")

            template_vmid = proxmox_service.find_template_vmid(vm_def["template"])
            new_vmid = proxmox_service.get_next_vmid()
            upid = proxmox_service.clone_template(
                template_vmid=template_vmid,
                new_vmid=new_vmid,
                name=vm_name,
            )

            success = proxmox_service.wait_for_task(upid, timeout=300)
            if not success:
                raise Exception(f"Clone failed for {vm_name} (VMID {new_vmid})")

            _log(db, deployment_id, f"VM {vm_name} clonée (VMID: {new_vmid})", phase="provisioning")

            # Configure specs
            specs = vm_def.get("default_specs", {})
            overrides = (deployment.vm_specs_override or {}).get(vm_def["name"], {})
            specs.update(overrides)

            # Resolve VLAN (int or None)
            raw_vlan = (deployment.network_config or {}).get("vlan_id") or settings.default_vlan_id
            vlan_tag = int(raw_vlan) if raw_vlan else None

            proxmox_service.configure_vm(
                vmid=new_vmid,
                cores=specs.get("cores", 2),
                memory=specs.get("ram", 4096),
                vlan_tag=vlan_tag,
            )

            vm_record = DeployedVM(
                deployment_id=deployment_id,
                vm_name=vm_name,
                proxmox_vmid=new_vmid,
                template_used=vm_def["template"],
                status="created",
                roles=vm_def["roles"],
                specs=specs,
            )
            db.add(vm_record)
            db.commit()
            vm_records.append((vm_record, vm_def))

        # ── Step 5: Start all VMs ──
        _log(db, deployment_id, "Démarrage des VMs...", phase="provisioning")
        for vm_record, _ in vm_records:
            proxmox_service.start_vm(vm_record.proxmox_vmid)
            vm_record.status = "starting"
            db.commit()

        # ── Step 6: Wait for boot ──
        wait = settings.vm_boot_wait_seconds
        _log(
            db, deployment_id,
            f"Attente du démarrage des VMs ({wait}s)...",
            phase="provisioning",
        )
        time.sleep(wait)

        # ── Step 7: Run Ansible (in dependency order) ──
        deployment.status = "configuring"
        db.commit()

        sorted_records = _topological_sort(vm_records)

        for vm_record, vm_def in sorted_records:
            # Get IP via Proxmox agent (with retries)
            if not vm_record.ip_address:
                _wait_for_ip(
                    db, deployment_id, vm_record,
                    retry_count=settings.vm_ip_retry_count,
                    retry_interval=settings.vm_ip_retry_interval,
                )

            if not vm_record.ip_address:
                vm_record.status = "failed"
                db.commit()
                _log(
                    db, deployment_id,
                    f"✗ {vm_record.vm_name}: IP introuvable, configuration impossible",
                    level="error",
                    phase="configuring",
                )
                continue

            if not vm_record.roles:
                vm_record.status = "configured"
                db.commit()
                continue

            _log(
                db, deployment_id,
                f"Configuration de {vm_record.vm_name} ({vm_record.ip_address}): "
                f"{', '.join(vm_record.roles)}",
                phase="configuring",
            )

            result = ansible_service.run_roles(
                host_ip=vm_record.ip_address,
                roles=vm_record.roles,
                os_type=vm_def.get("os_type", "linux"),
                extra_vars={
                    "deployment_name": deployment.name,
                    "vm_name": vm_record.vm_name,
                    "domain_name": (deployment.network_config or {}).get(
                        "domain", "lab.local"
                    ),
                    **stack_data.get("default_vars", {}),
                },
            )

            if result["status"] == "successful":
                vm_record.status = "configured"
                _log(
                    db, deployment_id,
                    f"✓ {vm_record.vm_name} configurée avec succès",
                    level="success",
                    phase="configuring",
                )
            else:
                vm_record.status = "failed"
                _log(
                    db, deployment_id,
                    f"✗ Échec de la configuration de {vm_record.vm_name} "
                    f"(rc={result.get('rc')})",
                    level="error",
                    phase="configuring",
                )
            db.commit()

        # ── Step 8: Final status ──
        failed_vms = [r for r, _ in vm_records if r.status == "failed"]
        if failed_vms:
            _update_status(
                db, deployment_id, "partial",
                f"{len(failed_vms)} VM(s) en échec",
            )
            _log(
                db, deployment_id,
                "Déploiement partiel — certaines VMs ont échoué",
                level="warn",
            )
        else:
            _update_status(db, deployment_id, "running")
            _log(
                db, deployment_id,
                "Déploiement terminé avec succès !",
                level="success",
            )

        return {"status": "success", "deployment_id": deployment_id}

    except Exception as e:
        logger.exception(f"Deployment {deployment_id} failed")
        _update_status(db, deployment_id, "failed", str(e))
        _log(db, deployment_id, f"Erreur fatale: {e}", level="error", phase="error")
        return {"status": "error", "message": str(e)}

    finally:
        db.close()
