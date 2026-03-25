"""Deployment orchestrator — Celery task that runs the full pipeline."""

import time
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.models.models import Deployment, DeployedVM, DeploymentLog
from app.services.proxmox_service import proxmox_service
from app.services.ansible_service import ansible_service
from app.services.stack_loader import get_stack_by_slug, resolve_services_to_vms

settings = get_settings()

# Celery tasks use sync DB access (not async)
sync_engine = create_engine(settings.database_url.replace("+aiosqlite", "").replace("+asyncpg", ""))
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
        if status == "running":
            deploy.completed_at = datetime.now(timezone.utc)
        db.commit()


@celery_app.task(bind=True, name="deploy_stack")
def deploy_stack_task(self, deployment_id: str):
    """
    Main deployment pipeline:
    1. Load stack definition
    2. Resolve services → VMs
    3. Clone templates on Proxmox
    4. Configure VMs (specs, network)
    5. Start VMs
    6. Wait for VMs to boot
    7. Run Ansible roles on each VM (respecting dependencies)
    8. Mark deployment as running
    """
    db = SyncSession()

    try:
        deployment = db.query(Deployment).get(deployment_id)
        if not deployment:
            logger.error(f"Deployment {deployment_id} not found")
            return {"status": "error", "message": "Deployment not found"}

        # Update status
        deployment.status = "provisioning"
        deployment.started_at = datetime.now(timezone.utc)
        db.commit()

        _log(db, deployment_id, "Démarrage du déploiement", phase="init")

        # ── Step 1: Load stack ──
        stack_def = db.query(
            __import__("app.models.models", fromlist=["StackDefinition"]).StackDefinition
        ).get(deployment.stack_id)

        stack_data = get_stack_by_slug(stack_def.slug if stack_def else "")
        if not stack_data:
            raise Exception(f"Stack definition not found: {stack_def.slug if stack_def else 'unknown'}")

        _log(db, deployment_id, f"Stack chargée: {stack_data['name']}", phase="init")

        # ── Step 2: Resolve VMs ──
        needed_vms = resolve_services_to_vms(stack_data, deployment.selected_services)
        _log(
            db, deployment_id,
            f"{len(needed_vms)} VM(s) à provisionner",
            phase="provisioning",
        )

        # ── Step 3 & 4: Clone and configure each VM ──
        vm_records = []
        for vm_def in needed_vms:
            vm_name = f"{deployment.name}-{vm_def['name']}".lower().replace(" ", "-")

            _log(db, deployment_id, f"Clonage de {vm_name}...", phase="provisioning")

            # Find template
            template_vmid = proxmox_service.find_template_vmid(vm_def["template"])
            if template_vmid is None:
                raise Exception(
                    f"Template '{vm_def['template']}' introuvable sur Proxmox"
                )

            # Get next VMID and clone
            new_vmid = proxmox_service.get_next_vmid()
            upid = proxmox_service.clone_template(
                template_vmid=template_vmid,
                new_vmid=new_vmid,
                name=vm_name,
            )

            # Wait for clone to finish
            success = proxmox_service.wait_for_task(upid, timeout=300)
            if not success:
                raise Exception(f"Clone failed for {vm_name} (VMID {new_vmid})")

            _log(db, deployment_id, f"VM {vm_name} clonée (VMID: {new_vmid})", phase="provisioning")

            # Configure specs
            specs = vm_def.get("default_specs", {})
            # Apply overrides if any
            overrides = (deployment.vm_specs_override or {}).get(vm_def["name"], {})
            specs.update(overrides)

            proxmox_service.configure_vm(
                vmid=new_vmid,
                cores=specs.get("cores", 2),
                memory=specs.get("ram", 4096),
                vlan_tag=(deployment.network_config or {}).get("vlan_id"),
            )

            # Create DB record
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

        # ── Step 6: Wait for boot (basic delay — replace with agent check later) ──
        _log(db, deployment_id, "Attente du démarrage des VMs (120s)...", phase="provisioning")
        time.sleep(120)

        # TODO: Replace with actual connectivity check (ping, WinRM test, SSH test)

        # ── Step 7: Run Ansible ──
        deployment.status = "configuring"
        db.commit()

        # Sort VMs by dependency order
        vm_name_map = {v["name"]: (rec, vdef) for rec, vdef in vm_records for v in [vdef]}

        for vm_record, vm_def in vm_records:
            # Check dependencies
            for dep_name in vm_def.get("depends_on", []):
                dep_rec = next(
                    (r for r, d in vm_records if d["name"] == dep_name), None
                )
                if dep_rec and dep_rec.status != "configured":
                    _log(
                        db, deployment_id,
                        f"Attente de {dep_name} avant de configurer {vm_def['name']}",
                        phase="configuring",
                    )
                    # Simple wait — in production, use a proper DAG scheduler
                    time.sleep(30)

            if not vm_record.ip_address:
                # Try to get IP from Proxmox agent
                try:
                    agent_info = proxmox_service.node.qemu(
                        vm_record.proxmox_vmid
                    ).agent("network-get-interfaces").get()
                    for iface in agent_info.get("result", []):
                        for addr in iface.get("ip-addresses", []):
                            if addr.get("ip-address-type") == "ipv4" and not addr[
                                "ip-address"
                            ].startswith("127."):
                                vm_record.ip_address = addr["ip-address"]
                                db.commit()
                                break
                except Exception:
                    _log(
                        db, deployment_id,
                        f"Impossible de récupérer l'IP de {vm_record.vm_name}",
                        level="warn",
                        phase="configuring",
                    )

            if vm_record.ip_address and vm_record.roles:
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
                        f"✗ Échec de la configuration de {vm_record.vm_name}",
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
            _log(db, deployment_id, "Déploiement partiel — certaines VMs ont échoué", level="warn")
        else:
            _update_status(db, deployment_id, "running")
            _log(db, deployment_id, "Déploiement terminé avec succès !", level="success")

        return {"status": "success", "deployment_id": deployment_id}

    except Exception as e:
        logger.exception(f"Deployment {deployment_id} failed")
        _update_status(db, deployment_id, "failed", str(e))
        _log(db, deployment_id, f"Erreur fatale: {e}", level="error", phase="error")
        return {"status": "error", "message": str(e)}

    finally:
        db.close()
