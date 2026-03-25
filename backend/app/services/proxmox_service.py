"""Proxmox VE API client for VM lifecycle management."""

from typing import Optional

from loguru import logger
from proxmoxer import ProxmoxAPI

from app.core.config import get_settings


class ProxmoxService:
    """Wrapper around the Proxmox API for stack deployment operations."""

    def __init__(self):
        self.settings = get_settings()
        self._api: Optional[ProxmoxAPI] = None

    @property
    def api(self) -> ProxmoxAPI:
        if self._api is None:
            self._api = ProxmoxAPI(
                self.settings.proxmox_host,
                port=self.settings.proxmox_port,
                user=self.settings.proxmox_user,
                token_name=self.settings.proxmox_token_name,
                token_value=self.settings.proxmox_token_value,
                verify_ssl=self.settings.proxmox_verify_ssl,
                service="PVE",
            )
        return self._api

    @property
    def node(self):
        return self.api.nodes(self.settings.proxmox_default_node)

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------
    def get_node_status(self) -> dict:
        """Get Proxmox node resource usage."""
        try:
            status = self.node.status.get()
            return {
                "online": True,
                "cpu_usage": status.get("cpu", 0),
                "memory_used": status.get("memory", {}).get("used", 0),
                "memory_total": status.get("memory", {}).get("total", 0),
                "uptime": status.get("uptime", 0),
            }
        except Exception as e:
            logger.error(f"Proxmox unreachable: {e}")
            return {"online": False, "error": str(e)}

    def list_templates(self) -> list[dict]:
        """List available VM templates on the node."""
        try:
            vms = self.node.qemu.get()
            return [
                {
                    "vmid": vm["vmid"],
                    "name": vm.get("name", ""),
                    "status": vm.get("status", ""),
                    "template": vm.get("template", 0),
                }
                for vm in vms
                if vm.get("template", 0) == 1
            ]
        except Exception as e:
            logger.error(f"Failed to list templates: {e}")
            return []

    def get_next_vmid(self) -> int:
        """Get the next available VMID from Proxmox."""
        return int(self.api.cluster.nextid.get())

    # ------------------------------------------------------------------
    # VM lifecycle
    # ------------------------------------------------------------------
    def clone_template(
        self,
        template_vmid: int,
        new_vmid: int,
        name: str,
        full_clone: bool = True,
        target_storage: Optional[str] = None,
    ) -> str:
        """Clone a VM template. Returns the UPID of the clone task."""
        params = {
            "newid": new_vmid,
            "name": name,
            "full": int(full_clone),
        }
        if target_storage:
            params["target"] = target_storage

        upid = self.node.qemu(template_vmid).clone.create(**params)
        logger.info(f"Cloning template {template_vmid} → VM {new_vmid} ({name})")
        return upid

    def configure_vm(
        self,
        vmid: int,
        cores: int = 2,
        memory: int = 4096,
        bridge: Optional[str] = None,
        vlan_tag: Optional[int] = None,
        ip_config: Optional[str] = None,
        ci_user: Optional[str] = None,
        ci_password: Optional[str] = None,
        sshkeys: Optional[str] = None,
    ) -> None:
        """Reconfigure a cloned VM (CPU, RAM, network, cloud-init)."""
        config = {
            "cores": cores,
            "memory": memory,
        }

        # Network
        net_value = f"virtio,bridge={bridge or self.settings.proxmox_default_bridge}"
        if vlan_tag:
            net_value += f",tag={vlan_tag}"
        config["net0"] = net_value

        # Cloud-init
        if ip_config:
            config["ipconfig0"] = ip_config
        if ci_user:
            config["ciuser"] = ci_user
        if ci_password:
            config["cipassword"] = ci_password
        if sshkeys:
            config["sshkeys"] = sshkeys

        self.node.qemu(vmid).config.put(**config)
        logger.info(f"Configured VM {vmid}: {cores} cores, {memory}MB RAM")

    def start_vm(self, vmid: int) -> str:
        """Start a VM. Returns the UPID."""
        upid = self.node.qemu(vmid).status.start.create()
        logger.info(f"Starting VM {vmid}")
        return upid

    def stop_vm(self, vmid: int) -> str:
        """Stop a VM gracefully."""
        upid = self.node.qemu(vmid).status.shutdown.create()
        logger.info(f"Stopping VM {vmid}")
        return upid

    def destroy_vm(self, vmid: int, purge: bool = True) -> str:
        """Destroy a VM and optionally purge its disks."""
        # Stop first if running
        try:
            status = self.node.qemu(vmid).status.current.get()
            if status.get("status") == "running":
                self.node.qemu(vmid).status.stop.create()
        except Exception:
            pass

        upid = self.node.qemu(vmid).delete(purge=int(purge))
        logger.info(f"Destroyed VM {vmid}")
        return upid

    def get_vm_status(self, vmid: int) -> dict:
        """Get current status of a VM."""
        try:
            info = self.node.qemu(vmid).status.current.get()
            return {
                "vmid": vmid,
                "status": info.get("status", "unknown"),
                "cpu": info.get("cpu", 0),
                "mem": info.get("mem", 0),
                "maxmem": info.get("maxmem", 0),
                "uptime": info.get("uptime", 0),
            }
        except Exception as e:
            return {"vmid": vmid, "status": "error", "error": str(e)}

    def wait_for_task(self, upid: str, timeout: int = 300) -> bool:
        """Block until a Proxmox task completes."""
        import time

        start = time.time()
        while time.time() - start < timeout:
            task = self.node.tasks(upid).status.get()
            if task.get("status") == "stopped":
                return task.get("exitstatus") == "OK"
            time.sleep(2)
        logger.error(f"Task {upid} timed out after {timeout}s")
        return False

    # ------------------------------------------------------------------
    # Template resolution
    # ------------------------------------------------------------------
    def find_template_vmid(self, template_name: str) -> Optional[int]:
        """Find a template VMID by name."""
        templates = self.list_templates()
        for tpl in templates:
            if tpl["name"] == template_name:
                return tpl["vmid"]
        return None


# Singleton
proxmox_service = ProxmoxService()
