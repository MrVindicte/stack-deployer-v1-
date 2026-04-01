"""Proxmox VE API client for VM lifecycle management."""

import time
import urllib.parse
from typing import Optional

from loguru import logger
from proxmoxer import ProxmoxAPI

from app.core.config import get_settings

# ---------------------------------------------------------------------------
# Cloud image registry — URL + default user for each OS "template" name
# ---------------------------------------------------------------------------
CLOUD_IMAGES = {
    "debian12-tpl": {
        "url": "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2",
        "os_type": "l26",
        "ci_user": "root",
    },
    "debian11-tpl": {
        "url": "https://cloud.debian.org/images/cloud/bullseye/latest/debian-11-generic-amd64.qcow2",
        "os_type": "l26",
        "ci_user": "root",
    },
    "ubuntu2204-tpl": {
        "url": "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img",
        "os_type": "l26",
        "ci_user": "ubuntu",
    },
    "ubuntu2404-tpl": {
        "url": "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img",
        "os_type": "l26",
        "ci_user": "ubuntu",
    },
}


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

    def list_cloud_images(self) -> list[str]:
        """List supported cloud image names."""
        return list(CLOUD_IMAGES.keys())

    def get_next_vmid(self) -> int:
        """Get the next available VMID from Proxmox."""
        return int(self.api.cluster.nextid.get())

    # ------------------------------------------------------------------
    # Cloud image helpers
    # ------------------------------------------------------------------
    def _image_exists_on_storage(self, filename: str, storage: str = "local") -> bool:
        """Check if a cloud image is already downloaded on Proxmox storage."""
        try:
            content = self.node.storage(storage).content.get()
            for item in content:
                if filename in item.get("volid", ""):
                    return True
        except Exception:
            pass
        return False

    def download_cloud_image(self, template_name: str, storage: str = "local") -> str:
        """
        Download a cloud image to Proxmox storage if not already present.
        Returns the filename on storage.
        """
        image_info = CLOUD_IMAGES.get(template_name)
        if not image_info:
            raise ValueError(f"Unknown cloud image: {template_name}")

        url = image_info["url"]
        original_filename = url.rsplit("/", 1)[-1]
        # Proxmox ISO storage only accepts .iso and .img extensions
        filename = original_filename
        if filename.endswith(".qcow2"):
            filename = filename.replace(".qcow2", ".img")

        if self._image_exists_on_storage(filename, storage):
            logger.info(f"Cloud image {filename} already on {storage}")
            return filename

        logger.info(f"Downloading {filename} to {storage}...")
        upid = self.node.storage(storage).post(
            "download-url",
            content="iso",
            filename=filename,
            url=url,
        )
        if not self.wait_for_task(upid, timeout=600):
            raise Exception(f"Failed to download cloud image: {filename}")

        logger.info(f"Cloud image {filename} downloaded successfully")
        return filename

    def _exec_on_node(self, command: str, timeout: int = 600) -> str:
        """Execute a command on the Proxmox node via the API."""
        # Use the /nodes/{node}/execute or status endpoint isn't available,
        # so we use a qemu-exec workaround via the task API.
        # Actually, Proxmox doesn't have a generic exec API.
        # We use SSH from the Celery container to Proxmox to run commands.
        import subprocess
        host = self.settings.proxmox_host
        result = subprocess.run(
            [
                "ssh", "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=10",
                f"root@{host}",
                command,
            ],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            raise Exception(
                f"Command failed on Proxmox (rc={result.returncode}): "
                f"{result.stderr.strip()}"
            )
        return result.stdout.strip()

    def create_vm_from_cloud_image(
        self,
        vmid: int,
        name: str,
        template_name: str,
        cores: int = 2,
        memory: int = 4096,
        disk_size: int = 40,
        bridge: Optional[str] = None,
        vlan_tag: Optional[int] = None,
        ssh_public_key: Optional[str] = None,
        ci_password: Optional[str] = None,
        ci_user: Optional[str] = None,
    ) -> None:
        """
        Create a VM from a cloud image with cloud-init.
        No template needed — downloads the image and imports the disk.
        """
        image_info = CLOUD_IMAGES.get(template_name)
        if not image_info:
            raise ValueError(
                f"Unknown image '{template_name}'. "
                f"Available: {', '.join(CLOUD_IMAGES.keys())}"
            )

        storage = self.settings.proxmox_default_storage
        iso_storage = "local"

        # Step 1: Download image to Proxmox
        filename = self.download_cloud_image(template_name, iso_storage)
        # Path on Proxmox filesystem where ISOs are stored
        image_path = f"/var/lib/vz/template/iso/{filename}"

        # Step 2: Create empty VM via API
        net_value = f"virtio,bridge={bridge or self.settings.proxmox_default_bridge}"
        if vlan_tag:
            net_value += f",tag={vlan_tag}"

        self.node.qemu.create(
            vmid=vmid,
            name=name,
            ostype=image_info["os_type"],
            cores=cores,
            memory=memory,
            net0=net_value,
            scsihw="virtio-scsi-pci",
            serial0="socket",
            vga="serial0",
            agent="enabled=1",
        )
        logger.info(f"Created VM {vmid} ({name})")

        # Step 3: Import disk via SSH to Proxmox host
        # qm importdisk is not available via REST API
        logger.info(f"Importing disk from {filename} to VM {vmid}...")
        self._exec_on_node(
            f"qm importdisk {vmid} {image_path} {storage}"
        )
        logger.info(f"Disk imported for VM {vmid}")

        # Step 4: Attach the imported disk + cloud-init + boot order
        ci_user = ci_user or image_info["ci_user"]
        sshkeys = ""
        if ssh_public_key:
            sshkeys = urllib.parse.quote(ssh_public_key, safe="")

        config = {
            "scsi0": f"{storage}:vm-{vmid}-disk-0",
            "boot": "order=scsi0",
            "ide2": f"{storage}:cloudinit",
            "ciuser": ci_user,
            "ipconfig0": "ip=dhcp",
        }
        if ci_password:
            config["cipassword"] = ci_password
        if sshkeys:
            config["sshkeys"] = sshkeys

        self.node.qemu(vmid).config.put(**config)
        logger.info(f"Configured cloud-init for VM {vmid}")

        # Step 4b: Inject vendor cloud-init snippet to enable password auth
        if ci_password:
            snippet_content = (
                "#cloud-config\n"
                "ssh_pwauth: true\n"
                "disable_root: false\n"
                "runcmd:\n"
                "  - sed -i 's/^#\\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config\n"
                "  - sed -i 's/^#\\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config\n"
                "  - systemctl restart sshd || systemctl restart ssh\n"
            )
            snippet_name = f"sd-vm-{vmid}.yml"
            self._exec_on_node(
                f"mkdir -p /var/lib/vz/snippets && "
                f"cat > /var/lib/vz/snippets/{snippet_name} << 'CIEOF'\n"
                f"{snippet_content}CIEOF"
            )
            # vendor= merges with the Proxmox-generated user config
            self.node.qemu(vmid).config.put(
                cicustom=f"vendor=local:snippets/{snippet_name}"
            )
            logger.info(f"Injected password auth snippet for VM {vmid}")

        # Step 5: Resize disk to requested size
        self.node.qemu(vmid).resize.put(
            disk="scsi0",
            size=f"{disk_size}G",
        )
        logger.info(f"Resized scsi0 to {disk_size}G for VM {vmid}")

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
        # Force stop if running, then wait for it to actually stop
        try:
            status = self.node.qemu(vmid).status.current.get()
            if status.get("status") == "running":
                self.node.qemu(vmid).status.stop.create()  # force stop
                # Wait until VM is actually stopped
                for _ in range(30):
                    time.sleep(2)
                    st = self.node.qemu(vmid).status.current.get()
                    if st.get("status") == "stopped":
                        break
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
        start = time.time()
        while time.time() - start < timeout:
            task = self.node.tasks(upid).status.get()
            if task.get("status") == "stopped":
                return task.get("exitstatus") == "OK"
            time.sleep(2)
        logger.error(f"Task {upid} timed out after {timeout}s")
        return False

    # ------------------------------------------------------------------
    # Template resolution (legacy — still works if templates exist)
    # ------------------------------------------------------------------
    def find_template_vmid(self, template_name: str) -> Optional[int]:
        """Find a template VMID by name."""
        templates = self.list_templates()
        for tpl in templates:
            if tpl["name"] == template_name:
                return tpl["vmid"]
        return None

    def is_cloud_image(self, template_name: str) -> bool:
        """Check if a template name corresponds to a cloud image."""
        return template_name in CLOUD_IMAGES


# Singleton
proxmox_service = ProxmoxService()
