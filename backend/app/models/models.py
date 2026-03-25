"""Database models for Stack Deployer."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def gen_uuid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="user")  # admin | user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    deployments = relationship("Deployment", back_populates="user")


# ---------------------------------------------------------------------------
# Stack definition (metadata stored in DB, YAML is the source of truth)
# ---------------------------------------------------------------------------
class StackDefinition(Base):
    __tablename__ = "stack_definitions"

    id = Column(String, primary_key=True, default=gen_uuid)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False)  # windows | linux | hybrid | security
    icon = Column(String(50), default="server")
    version = Column(String(20), default="1.0.0")
    yaml_path = Column(String(500), nullable=False)  # Path to stack YAML file
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    deployments = relationship("Deployment", back_populates="stack")


# ---------------------------------------------------------------------------
# Deployment (a running instance of a stack)
# ---------------------------------------------------------------------------
class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(200), nullable=False)
    stack_id = Column(String, ForeignKey("stack_definitions.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(
        String(30),
        default="pending",
        index=True,
    )
    # Status flow: pending → provisioning → configuring → running → stopped → destroyed → failed
    selected_services = Column(JSON, nullable=False, default=list)
    vm_specs_override = Column(JSON, nullable=True)  # Optional per-VM overrides
    network_config = Column(JSON, nullable=True)
    celery_task_id = Column(String(255), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    stack = relationship("StackDefinition", back_populates="deployments")
    user = relationship("User", back_populates="deployments")
    vms = relationship("DeployedVM", back_populates="deployment", cascade="all, delete-orphan")
    logs = relationship("DeploymentLog", back_populates="deployment", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Individual VM within a deployment
# ---------------------------------------------------------------------------
class DeployedVM(Base):
    __tablename__ = "deployed_vms"

    id = Column(String, primary_key=True, default=gen_uuid)
    deployment_id = Column(String, ForeignKey("deployments.id"), nullable=False)
    vm_name = Column(String(100), nullable=False)
    proxmox_vmid = Column(Integer, nullable=True)
    template_used = Column(String(200), nullable=True)
    ip_address = Column(String(45), nullable=True)
    status = Column(String(30), default="pending")
    roles = Column(JSON, default=list)  # ["ad-ds", "dns", "dhcp"]
    specs = Column(JSON, nullable=True)  # {"cores": 2, "ram": 4096, "disk": 50}
    created_at = Column(DateTime, default=utcnow)

    deployment = relationship("Deployment", back_populates="vms")


# ---------------------------------------------------------------------------
# Deployment logs (streamed via WebSocket)
# ---------------------------------------------------------------------------
class DeploymentLog(Base):
    __tablename__ = "deployment_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deployment_id = Column(String, ForeignKey("deployments.id"), nullable=False)
    level = Column(String(10), default="info")  # info | warn | error | success
    phase = Column(String(50), nullable=True)  # provisioning | configuring | <role_name>
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=utcnow)

    deployment = relationship("Deployment", back_populates="logs")
