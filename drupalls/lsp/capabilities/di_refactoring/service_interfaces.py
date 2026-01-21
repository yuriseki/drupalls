"""
Service ID to interface mapping.

File: drupalls/lsp/capabilities/di_refactoring/service_interfaces.py
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ServiceInterfaceInfo:
    """Information about a service's interface."""

    interface_fqcn: str
    interface_short: str
    property_name: str
    use_statement: str


def get_service_interface(service_id: str, workspace_cache=None) -> ServiceInterfaceInfo | None:
    """Synthesize ServiceInterfaceInfo for service_id using WorkspaceCache.

    Returns None if the services cache does not contain a class for the
    service_id. Cache access is defensive and will not raise to callers.
    """
    try:
        if workspace_cache and hasattr(workspace_cache, "caches"):
            services_cache = workspace_cache.caches.get("services")
            if services_cache:
                service_def = services_cache.get(service_id)
                if service_def and service_def.class_name:
                    fqcn = service_def.class_name.lstrip("\\")
                    short = fqcn.split("\\")[-1]
                    prop = get_property_name(service_id)
                    use_stmt = f"use {fqcn};"
                    return ServiceInterfaceInfo(
                        interface_fqcn=fqcn,
                        interface_short=short,
                        property_name=prop,
                        use_statement=use_stmt,
                    )
    except Exception:
        # Cache lookups must never crash the refactoring flow
        pass

    return None


def get_property_name(service_id: str) -> str:
    """Get a property name for a service ID.

    Deterministically generate a camelCase property name from the service id.
    """
    parts = service_id.replace(".", "_").split("_")
    if not parts:
        return service_id
    return parts[0] + "".join(p.capitalize() for p in parts[1:])
