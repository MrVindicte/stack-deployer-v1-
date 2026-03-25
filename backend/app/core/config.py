"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "Stack Deployer"
    app_env: str = "development"
    secret_key: str = "change-me"
    debug: bool = True

    # Database
    database_url: str = "sqlite+aiosqlite:///./stack_deployer.db"

    # Proxmox
    proxmox_host: str = "192.168.1.100"
    proxmox_port: int = 8006
    proxmox_user: str = "root@pam"
    proxmox_token_name: str = "stack-deployer"
    proxmox_token_value: str = ""
    proxmox_verify_ssl: bool = False
    proxmox_default_node: str = "pve"
    proxmox_default_storage: str = "local-lvm"
    proxmox_default_bridge: str = "vmbr0"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Ansible
    ansible_roles_path: str = "./ansible/roles"
    ansible_inventory_path: str = "./ansible/inventories"
    ansible_private_key: str = "~/.ssh/id_ed25519"

    # Auth
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    first_admin_user: str = "admin"
    first_admin_password: str = "change-me"

    # Network defaults
    default_vlan_id: str = ""
    default_dns_server: str = "192.168.1.1"
    default_gateway: str = "192.168.1.1"
    default_subnet_mask: int = 24

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
