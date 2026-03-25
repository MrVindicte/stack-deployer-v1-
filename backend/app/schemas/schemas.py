"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


# ---------------------------------------------------------------------------
# Stack definitions
# ---------------------------------------------------------------------------
class ServiceInfo(BaseModel):
    """A selectable service/role within a stack."""
    id: str
    name: str
    description: str = ""
    required: bool = False  # If True, cannot be deselected
    depends_on: list[str] = []


class VMTemplate(BaseModel):
    """VM definition within a stack."""
    name: str
    template: str
    os_type: str = "windows"  # windows | linux
    roles: list[str] = []
    default_specs: dict = Field(default_factory=lambda: {"cores": 2, "ram": 4096, "disk": 50})
    depends_on: list[str] = []


class StackOut(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    category: str
    icon: str
    version: str
    services: list[ServiceInfo] = []
    vms: list[VMTemplate] = []

    model_config = {"from_attributes": True}


class StackListOut(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    category: str
    icon: str
    version: str
    vm_count: int = 0
    service_count: int = 0

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Deployments
# ---------------------------------------------------------------------------
class DeployRequest(BaseModel):
    """Request to deploy a stack."""
    stack_slug: str
    name: str = Field(..., min_length=1, max_length=200)
    selected_services: list[str]  # Service IDs to activate
    vm_specs_override: dict | None = None  # {"DC01": {"ram": 8192}}
    network_config: dict | None = None  # {"vlan_id": 10, "subnet": "10.0.1.0/24"}


class DeploymentOut(BaseModel):
    id: str
    name: str
    stack_slug: str
    stack_name: str
    status: str
    selected_services: list[str]
    vm_count: int = 0
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None

    model_config = {"from_attributes": True}


class VMOut(BaseModel):
    id: str
    vm_name: str
    proxmox_vmid: int | None
    ip_address: str | None
    status: str
    roles: list[str]
    specs: dict | None

    model_config = {"from_attributes": True}


class DeploymentDetailOut(DeploymentOut):
    vms: list[VMOut] = []


class LogEntry(BaseModel):
    level: str
    phase: str | None
    message: str
    timestamp: datetime

    model_config = {"from_attributes": True}
