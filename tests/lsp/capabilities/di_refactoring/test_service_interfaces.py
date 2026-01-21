"""
Tests for service_interfaces module.

File: tests/lsp/capabilities/di_refactoring/test_service_interfaces.py
"""
from __future__ import annotations

import pytest
from drupalls.lsp.capabilities.di_refactoring.service_interfaces import (
    ServiceInterfaceInfo,
    SERVICE_INTERFACES,
    get_service_interface,
    get_property_name,
)


# ============================================================================
# Tests for get_service_interface
# ============================================================================

class TestGetServiceInterface:
    """Tests for get_service_interface function."""

    def test_get_known_service_interface(self) -> None:
        """Test getting interface info for a known service."""
        info = get_service_interface("entity_type.manager")
        
        assert info is not None
        assert info.interface_short == "EntityTypeManagerInterface"
        assert info.property_name == "entityTypeManager"
        assert "EntityTypeManagerInterface" in info.use_statement

    def test_get_messenger_interface(self) -> None:
        """Test getting interface info for messenger service."""
        info = get_service_interface("messenger")
        
        assert info is not None
        assert info.interface_short == "MessengerInterface"
        assert info.property_name == "messenger"

    def test_get_database_interface(self) -> None:
        """Test getting interface info for database service."""
        info = get_service_interface("database")
        
        assert info is not None
        assert info.interface_short == "Connection"
        assert info.property_name == "database"

    def test_get_unknown_service_returns_none(self) -> None:
        """Test that unknown service returns None."""
        info = get_service_interface("unknown.service.id")
        
        assert info is None

    def test_get_config_factory_interface(self) -> None:
        """Test getting interface info for config.factory service."""
        info = get_service_interface("config.factory")
        
        assert info is not None
        assert info.interface_short == "ConfigFactoryInterface"
        assert info.property_name == "configFactory"


# ============================================================================
# Tests for get_property_name
# ============================================================================

class TestGetPropertyName:
    """Tests for get_property_name function."""

    def test_get_property_name_known_service(self) -> None:
        """Test getting property name for known service."""
        name = get_property_name("entity_type.manager")
        
        assert name == "entityTypeManager"

    def test_get_property_name_unknown_service_simple(self) -> None:
        """Test property name generation for unknown simple service."""
        name = get_property_name("my_service")
        
        assert name == "myService"

    def test_get_property_name_unknown_service_dots(self) -> None:
        """Test property name generation for service with dots."""
        name = get_property_name("my.custom.service")
        
        assert name == "myCustomService"

    def test_get_property_name_unknown_service_mixed(self) -> None:
        """Test property name generation for service with dots and underscores."""
        name = get_property_name("my.custom_service.handler")
        
        assert name == "myCustomServiceHandler"

    def test_get_property_name_single_word(self) -> None:
        """Test property name for known single word service."""
        # "cache_factory" is a known service
        name = get_property_name("cache_factory")
        
        assert name == "cacheFactory"

    def test_get_property_name_unknown_single_word(self) -> None:
        """Test property name for unknown single word service."""
        name = get_property_name("myservice")
        
        assert name == "myservice"


# ============================================================================
# Tests for ServiceInterfaceInfo dataclass
# ============================================================================

class TestServiceInterfaceInfo:
    """Tests for ServiceInterfaceInfo dataclass."""

    def test_create_service_interface_info(self) -> None:
        """Test creating ServiceInterfaceInfo instance."""
        info = ServiceInterfaceInfo(
            interface_fqcn="Drupal\\Core\\Entity\\EntityTypeManagerInterface",
            interface_short="EntityTypeManagerInterface",
            property_name="entityTypeManager",
            use_statement="use Drupal\\Core\\Entity\\EntityTypeManagerInterface;",
        )
        
        assert info.interface_fqcn == "Drupal\\Core\\Entity\\EntityTypeManagerInterface"
        assert info.interface_short == "EntityTypeManagerInterface"
        assert info.property_name == "entityTypeManager"
        assert "use Drupal\\Core\\Entity\\EntityTypeManagerInterface" in info.use_statement


# ============================================================================
# Tests for SERVICE_INTERFACES constant
# ============================================================================

class TestServiceInterfaces:
    """Tests for SERVICE_INTERFACES mapping."""

    def test_service_interfaces_is_dict(self) -> None:
        """Test that SERVICE_INTERFACES is a dictionary."""
        assert isinstance(SERVICE_INTERFACES, dict)

    def test_service_interfaces_contains_common_services(self) -> None:
        """Test that common services are mapped."""
        expected_services = [
            "entity_type.manager",
            "database",
            "config.factory",
            "current_user",
            "messenger",
            "state",
        ]
        for service in expected_services:
            assert service in SERVICE_INTERFACES, f"Missing service: {service}"

    def test_service_interfaces_values_are_info_objects(self) -> None:
        """Test that all values are ServiceInterfaceInfo."""
        for service_id, info in SERVICE_INTERFACES.items():
            assert isinstance(info, ServiceInterfaceInfo), (
                f"{service_id} value is not ServiceInterfaceInfo"
            )

    def test_service_interfaces_use_statements_are_valid(self) -> None:
        """Test that use statements are properly formatted."""
        for service_id, info in SERVICE_INTERFACES.items():
            assert info.use_statement.startswith("use "), (
                f"{service_id} use statement doesn't start with 'use '"
            )
            assert info.use_statement.endswith(";"), (
                f"{service_id} use statement doesn't end with ';'"
            )

    def test_service_interfaces_property_names_are_camel_case(self) -> None:
        """Test that property names are in camelCase."""
        for service_id, info in SERVICE_INTERFACES.items():
            # Should start with lowercase
            assert info.property_name[0].islower(), (
                f"{service_id} property name doesn't start lowercase"
            )
            # Should not contain underscores
            assert "_" not in info.property_name, (
                f"{service_id} property name contains underscore"
            )
