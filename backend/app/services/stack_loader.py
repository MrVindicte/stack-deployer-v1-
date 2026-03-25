"""Stack loader — reads YAML stack definitions from disk."""

import os
from pathlib import Path
from typing import Optional

import yaml
from loguru import logger

from app.schemas.schemas import ServiceInfo, StackOut, VMTemplate

STACKS_DIR = Path(__file__).resolve().parent.parent.parent / "stacks"


_REQUIRED_STACK_FIELDS = ["slug", "name", "category", "services", "vms"]
_REQUIRED_SERVICE_FIELDS = ["id", "name", "roles"]
_REQUIRED_VM_FIELDS = ["name", "template", "roles"]


def _validate_stack(data: dict, filename: str) -> list[str]:
    """Return a list of validation error strings, empty if valid."""
    errors = []
    for field in _REQUIRED_STACK_FIELDS:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    for i, svc in enumerate(data.get("services", [])):
        for field in _REQUIRED_SERVICE_FIELDS:
            if field not in svc:
                errors.append(f"Service[{i}] missing field: '{field}'")

    for i, vm in enumerate(data.get("vms", [])):
        for field in _REQUIRED_VM_FIELDS:
            if field not in vm:
                errors.append(f"VM[{i}] missing field: '{field}'")

    return errors


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Stack file must be a YAML mapping, got {type(data).__name__}")
    return data


def load_all_stacks() -> list[dict]:
    """Scan the stacks/ directory and load every .yml/.yaml file."""
    stacks = []
    if not STACKS_DIR.exists():
        logger.warning(f"Stacks directory not found: {STACKS_DIR}")
        return stacks

    for entry in sorted(STACKS_DIR.iterdir()):
        if entry.is_file() and entry.suffix in (".yml", ".yaml"):
            try:
                data = _load_yaml(entry)
                errors = _validate_stack(data, entry.name)
                if errors:
                    for err in errors:
                        logger.error(f"Stack {entry.name} validation error: {err}")
                    logger.warning(f"Skipping invalid stack: {entry.name}")
                    continue
                data["_file"] = str(entry)
                stacks.append(data)
                logger.info(f"Loaded stack: {data.get('name', entry.stem)}")
            except Exception as e:
                logger.error(f"Failed to load stack {entry.name}: {e}")
    return stacks


def get_stack_by_slug(slug: str) -> Optional[dict]:
    """Load a single stack definition by its slug."""
    for stack in load_all_stacks():
        if stack.get("slug") == slug:
            return stack
    return None


def parse_stack(data: dict) -> StackOut:
    """Parse a raw YAML dict into a validated StackOut schema."""
    services = [
        ServiceInfo(**svc)
        for svc in data.get("services", [])
    ]
    vms = [
        VMTemplate(**vm)
        for vm in data.get("vms", [])
    ]
    return StackOut(
        id=data.get("id", data.get("slug", "")),
        slug=data["slug"],
        name=data["name"],
        description=data.get("description"),
        category=data.get("category", "other"),
        icon=data.get("icon", "server"),
        version=data.get("version", "1.0.0"),
        services=services,
        vms=vms,
    )


def resolve_services_to_vms(
    stack_data: dict, selected_service_ids: list[str]
) -> list[dict]:
    """
    Given a stack definition and selected services, determine which VMs
    are needed and what roles each VM should run.

    Returns a list of VM dicts with their resolved roles.
    """
    service_map = {svc["id"]: svc for svc in stack_data.get("services", [])}

    # Always include required services
    active_services = set(selected_service_ids)
    for svc in stack_data.get("services", []):
        if svc.get("required", False):
            active_services.add(svc["id"])

    # Resolve dependencies
    resolved = set()
    to_resolve = list(active_services)
    while to_resolve:
        sid = to_resolve.pop()
        if sid in resolved:
            continue
        resolved.add(sid)
        svc = service_map.get(sid, {})
        for dep in svc.get("depends_on", []):
            if dep not in resolved:
                to_resolve.append(dep)

    # Map services to VM roles
    role_to_service = {}
    for svc in stack_data.get("services", []):
        for role in svc.get("roles", []):
            role_to_service[role] = svc["id"]

    # Filter VMs: include a VM if any of its roles belong to a resolved service
    needed_vms = []
    for vm in stack_data.get("vms", []):
        vm_roles = []
        for role in vm.get("roles", []):
            svc_id = role_to_service.get(role)
            if svc_id and svc_id in resolved:
                vm_roles.append(role)
        if vm_roles:
            vm_copy = dict(vm)
            vm_copy["roles"] = vm_roles
            needed_vms.append(vm_copy)

    return needed_vms
