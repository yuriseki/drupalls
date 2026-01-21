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


# Mapping of common Drupal service IDs to their interfaces
SERVICE_INTERFACES: dict[str, ServiceInterfaceInfo] = {
    "entity_type.manager": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Core\\Entity\\EntityTypeManagerInterface",
        interface_short="EntityTypeManagerInterface",
        property_name="entityTypeManager",
        use_statement="use Drupal\\Core\\Entity\\EntityTypeManagerInterface;",
    ),
    "database": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Core\\Database\\Connection",
        interface_short="Connection",
        property_name="database",
        use_statement="use Drupal\\Core\\Database\\Connection;",
    ),
    "config.factory": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Core\\Config\\ConfigFactoryInterface",
        interface_short="ConfigFactoryInterface",
        property_name="configFactory",
        use_statement="use Drupal\\Core\\Config\\ConfigFactoryInterface;",
    ),
    "current_user": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Core\\Session\\AccountProxyInterface",
        interface_short="AccountProxyInterface",
        property_name="currentUser",
        use_statement="use Drupal\\Core\\Session\\AccountProxyInterface;",
    ),
    "messenger": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Core\\Messenger\\MessengerInterface",
        interface_short="MessengerInterface",
        property_name="messenger",
        use_statement="use Drupal\\Core\\Messenger\\MessengerInterface;",
    ),
    "logger.factory": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Core\\Logger\\LoggerChannelFactoryInterface",
        interface_short="LoggerChannelFactoryInterface",
        property_name="loggerFactory",
        use_statement="use Drupal\\Core\\Logger\\LoggerChannelFactoryInterface;",
    ),
    "state": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Core\\State\\StateInterface",
        interface_short="StateInterface",
        property_name="state",
        use_statement="use Drupal\\Core\\State\\StateInterface;",
    ),
    "language_manager": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Core\\Language\\LanguageManagerInterface",
        interface_short="LanguageManagerInterface",
        property_name="languageManager",
        use_statement="use Drupal\\Core\\Language\\LanguageManagerInterface;",
    ),
    "module_handler": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Core\\Extension\\ModuleHandlerInterface",
        interface_short="ModuleHandlerInterface",
        property_name="moduleHandler",
        use_statement="use Drupal\\Core\\Extension\\ModuleHandlerInterface;",
    ),
    "datetime.time": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Component\\Datetime\\TimeInterface",
        interface_short="TimeInterface",
        property_name="time",
        use_statement="use Drupal\\Component\\Datetime\\TimeInterface;",
    ),
    "request_stack": ServiceInterfaceInfo(
        interface_fqcn="Symfony\\Component\\HttpFoundation\\RequestStack",
        interface_short="RequestStack",
        property_name="requestStack",
        use_statement="use Symfony\\Component\\HttpFoundation\\RequestStack;",
    ),
    "current_route_match": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Core\\Routing\\RouteMatchInterface",
        interface_short="RouteMatchInterface",
        property_name="routeMatch",
        use_statement="use Drupal\\Core\\Routing\\RouteMatchInterface;",
    ),
    "http_client": ServiceInterfaceInfo(
        interface_fqcn="GuzzleHttp\\ClientInterface",
        interface_short="ClientInterface",
        property_name="httpClient",
        use_statement="use GuzzleHttp\\ClientInterface;",
    ),
    "cache_factory": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Core\\Cache\\CacheFactoryInterface",
        interface_short="CacheFactoryInterface",
        property_name="cacheFactory",
        use_statement="use Drupal\\Core\\Cache\\CacheFactoryInterface;",
    ),
    "token": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Core\\Utility\\Token",
        interface_short="Token",
        property_name="token",
        use_statement="use Drupal\\Core\\Utility\\Token;",
    ),
}


def get_service_interface(service_id: str) -> ServiceInterfaceInfo | None:
    """Get interface info for a service ID."""
    return SERVICE_INTERFACES.get(service_id)


def get_property_name(service_id: str) -> str:
    """Get a property name for a service ID."""
    info = SERVICE_INTERFACES.get(service_id)
    if info:
        return info.property_name

    # Generate from service ID
    parts = service_id.replace(".", "_").split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])
