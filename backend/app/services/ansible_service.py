"""Ansible runner service — executes playbooks to configure VMs."""

import json
import tempfile
from pathlib import Path
from typing import Callable, Optional

import ansible_runner
from loguru import logger

from app.core.config import get_settings

settings = get_settings()
ROLES_PATH = Path(settings.ansible_roles_path).resolve()


class AnsibleService:
    """Run Ansible playbooks/roles against deployed VMs."""

    def run_roles(
        self,
        host_ip: str,
        roles: list[str],
        extra_vars: dict | None = None,
        os_type: str = "linux",
        on_event: Optional[Callable[[dict], None]] = None,
    ) -> dict:
        """
        Run a list of Ansible roles against a single host.

        Args:
            host_ip: IP address of the target VM
            roles: List of role names to apply (e.g. ["ad-ds", "dns"])
            extra_vars: Additional variables for the playbook
            os_type: "linux" or "windows" (determines connection type)
            on_event: Optional callback for streaming events

        Returns:
            dict with status, stdout, and stats
        """
        # Build dynamic inventory
        connection = "winrm" if os_type == "windows" else "ssh"
        inventory = {
            "all": {
                "hosts": {
                    host_ip: {
                        "ansible_connection": connection,
                        "ansible_host": host_ip,
                    }
                },
                "vars": {
                    **(
                        {
                            "ansible_winrm_transport": "ntlm",
                            "ansible_winrm_server_cert_validation": "ignore",
                            "ansible_port": 5986,
                            "ansible_user": settings.ansible_winrm_user,
                            "ansible_password": settings.ansible_winrm_password,
                        }
                        if os_type == "windows"
                        else {
                            "ansible_ssh_private_key_file": settings.ansible_private_key,
                            "ansible_user": settings.ansible_user,
                            "ansible_ssh_extra_args": "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
                        }
                    ),
                },
            }
        }

        # Build inline playbook from roles
        playbook = [
            {
                "name": f"Configure {host_ip} with roles: {', '.join(roles)}",
                "hosts": "all",
                "become": os_type == "linux",
                "gather_facts": True,
                "roles": [{"role": role} for role in roles],
                "vars": extra_vars or {},
            }
        ]

        # Write temp files
        with tempfile.TemporaryDirectory(prefix="sd_ansible_") as tmpdir:
            tmppath = Path(tmpdir)

            inv_file = tmppath / "inventory.json"
            inv_file.write_text(json.dumps(inventory))

            pb_file = tmppath / "playbook.yml"
            import yaml
            pb_file.write_text(yaml.dump(playbook, default_flow_style=False))

            logger.info(
                f"Running Ansible: host={host_ip}, roles={roles}, os={os_type}"
            )

            # Run
            runner = ansible_runner.run(
                playbook=str(pb_file),
                inventory=str(inv_file),
                roles_path=str(ROLES_PATH),
                quiet=False,
                event_handler=on_event,
            )

            result = {
                "status": runner.status,  # successful | failed | canceled
                "rc": runner.rc,
                "stats": runner.stats,
            }

            if runner.status != "successful":
                logger.error(
                    f"Ansible failed on {host_ip}: rc={runner.rc}"
                )
                # Capture last few events for debugging
                result["last_events"] = [
                    e.get("event_data", {}).get("res", {})
                    for e in list(runner.events)[-5:]
                ]
            else:
                logger.info(f"Ansible successful on {host_ip}")

            return result

    def check_role_exists(self, role_name: str) -> bool:
        """Verify that an Ansible role exists in the roles path."""
        role_path = ROLES_PATH / role_name
        return role_path.is_dir() and (role_path / "tasks").is_dir()

    def list_available_roles(self) -> list[str]:
        """List all available Ansible roles."""
        if not ROLES_PATH.exists():
            return []
        return [
            d.name
            for d in ROLES_PATH.iterdir()
            if d.is_dir() and (d / "tasks").is_dir()
        ]


ansible_service = AnsibleService()
