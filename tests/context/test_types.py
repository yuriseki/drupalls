"""
Comprehensive tests for drupalls/context/types.py

Tests the DrupalClassType enum with:
- All enum values presence and correctness
- Enum comparison and usage patterns
- String representation and value access
- Iteration and membership testing
"""
from __future__ import annotations

import pytest

from drupalls.context.types import DrupalClassType


class TestDrupalClassTypeValues:
    """Tests for DrupalClassType enum values."""

    def test_controller_value(self):
        """Test CONTROLLER enum has correct value."""
        assert DrupalClassType.CONTROLLER.value == "controller"

    def test_form_value(self):
        """Test FORM enum has correct value."""
        assert DrupalClassType.FORM.value == "form"

    def test_plugin_value(self):
        """Test PLUGIN enum has correct value."""
        assert DrupalClassType.PLUGIN.value == "plugin"

    def test_entity_value(self):
        """Test ENTITY enum has correct value."""
        assert DrupalClassType.ENTITY.value == "entity"

    def test_service_value(self):
        """Test SERVICE enum has correct value."""
        assert DrupalClassType.SERVICE.value == "service"

    def test_event_subscriber_value(self):
        """Test EVENT_SUBSCRIBER enum has correct value."""
        assert DrupalClassType.EVENT_SUBSCRIBER.value == "subscriber"

    def test_access_checker_value(self):
        """Test ACCESS_CHECKER enum has correct value."""
        assert DrupalClassType.ACCESS_CHECKER.value == "access"

    def test_block_value(self):
        """Test BLOCK enum has correct value."""
        assert DrupalClassType.BLOCK.value == "block"

    def test_field_formatter_value(self):
        """Test FIELD_FORMATTER enum has correct value."""
        assert DrupalClassType.FIELD_FORMATTER.value == "formatter"

    def test_field_widget_value(self):
        """Test FIELD_WIDGET enum has correct value."""
        assert DrupalClassType.FIELD_WIDGET.value == "widget"

    def test_migration_value(self):
        """Test MIGRATION enum has correct value."""
        assert DrupalClassType.MIGRATION.value == "migration"

    def test_queue_worker_value(self):
        """Test QUEUE_WORKER enum has correct value."""
        assert DrupalClassType.QUEUE_WORKER.value == "queue_worker"

    def test_constraint_value(self):
        """Test CONSTRAINT enum has correct value."""
        assert DrupalClassType.CONSTRAINT.value == "constraint"

    def test_unknown_value(self):
        """Test UNKNOWN enum has correct value."""
        assert DrupalClassType.UNKNOWN.value == "unknown"


class TestDrupalClassTypeCompleteness:
    """Tests for enum completeness and consistency."""

    def test_all_expected_members_exist(self):
        """Test all expected enum members are defined."""
        expected_members = {
            "CONTROLLER",
            "FORM",
            "PLUGIN",
            "ENTITY",
            "SERVICE",
            "EVENT_SUBSCRIBER",
            "ACCESS_CHECKER",
            "BLOCK",
            "FIELD_FORMATTER",
            "FIELD_WIDGET",
            "MIGRATION",
            "QUEUE_WORKER",
            "CONSTRAINT",
            "UNKNOWN",
        }
        actual_members = {member.name for member in DrupalClassType}
        assert actual_members == expected_members

    def test_enum_member_count(self):
        """Test the total number of enum members."""
        assert len(DrupalClassType) == 14

    def test_all_values_are_unique(self):
        """Test all enum values are unique."""
        values = [member.value for member in DrupalClassType]
        assert len(values) == len(set(values))

    def test_all_values_are_strings(self):
        """Test all enum values are strings."""
        for member in DrupalClassType:
            assert isinstance(member.value, str)

    def test_all_values_are_lowercase(self):
        """Test all enum values are lowercase."""
        for member in DrupalClassType:
            assert member.value == member.value.lower()


class TestDrupalClassTypeComparison:
    """Tests for enum comparison operations."""

    def test_equality_same_member(self):
        """Test enum member equals itself."""
        assert DrupalClassType.CONTROLLER == DrupalClassType.CONTROLLER

    def test_inequality_different_members(self):
        """Test different enum members are not equal."""
        assert DrupalClassType.CONTROLLER != DrupalClassType.FORM

    def test_identity_same_member(self):
        """Test enum member is identical to itself."""
        assert DrupalClassType.PLUGIN is DrupalClassType.PLUGIN

    def test_not_equal_to_string_value(self):
        """Test enum member is not equal to its string value."""
        assert DrupalClassType.CONTROLLER != "controller"

    def test_not_equal_to_none(self):
        """Test enum member is not equal to None."""
        assert DrupalClassType.UNKNOWN is not None
        assert DrupalClassType.UNKNOWN != None  # noqa: E711

    def test_not_equal_to_integer(self):
        """Test enum member is not equal to an integer."""
        assert DrupalClassType.CONTROLLER != 1


class TestDrupalClassTypeUsage:
    """Tests for practical enum usage patterns."""

    def test_lookup_by_name(self):
        """Test enum lookup by member name."""
        assert DrupalClassType["CONTROLLER"] == DrupalClassType.CONTROLLER
        assert DrupalClassType["FORM"] == DrupalClassType.FORM

    def test_lookup_by_value(self):
        """Test enum lookup by value."""
        assert DrupalClassType("controller") == DrupalClassType.CONTROLLER
        assert DrupalClassType("form") == DrupalClassType.FORM

    def test_lookup_invalid_name_raises_keyerror(self):
        """Test looking up invalid name raises KeyError."""
        with pytest.raises(KeyError):
            DrupalClassType["NONEXISTENT"]

    def test_lookup_invalid_value_raises_valueerror(self):
        """Test looking up invalid value raises ValueError."""
        with pytest.raises(ValueError):
            DrupalClassType("nonexistent")

    def test_member_name_attribute(self):
        """Test accessing the name attribute."""
        assert DrupalClassType.CONTROLLER.name == "CONTROLLER"
        assert DrupalClassType.FIELD_FORMATTER.name == "FIELD_FORMATTER"

    def test_iteration(self):
        """Test iterating over enum members."""
        members = list(DrupalClassType)
        assert len(members) == 14
        assert DrupalClassType.CONTROLLER in members
        assert DrupalClassType.UNKNOWN in members

    def test_membership_check(self):
        """Test membership check in enum."""
        assert DrupalClassType.SERVICE in DrupalClassType
        assert DrupalClassType.BLOCK in DrupalClassType


class TestDrupalClassTypeStringRepresentation:
    """Tests for string representation of enum members."""

    def test_str_representation(self):
        """Test str() representation of enum."""
        assert str(DrupalClassType.CONTROLLER) == "DrupalClassType.CONTROLLER"
        assert str(DrupalClassType.UNKNOWN) == "DrupalClassType.UNKNOWN"

    def test_repr_representation(self):
        """Test repr() representation of enum."""
        assert repr(DrupalClassType.CONTROLLER) == "<DrupalClassType.CONTROLLER: 'controller'>"

    def test_value_in_format_string(self):
        """Test using enum value in format string."""
        result = f"Class type is: {DrupalClassType.PLUGIN.value}"
        assert result == "Class type is: plugin"


class TestDrupalClassTypeInCollections:
    """Tests for using enum in collections."""

    def test_as_dict_key(self):
        """Test using enum as dictionary key."""
        mapping = {
            DrupalClassType.CONTROLLER: "controllers",
            DrupalClassType.FORM: "forms",
        }
        assert mapping[DrupalClassType.CONTROLLER] == "controllers"
        assert mapping[DrupalClassType.FORM] == "forms"

    def test_in_set(self):
        """Test using enum in a set."""
        class_types = {DrupalClassType.CONTROLLER, DrupalClassType.FORM}
        assert DrupalClassType.CONTROLLER in class_types
        assert DrupalClassType.PLUGIN not in class_types

    def test_in_list(self):
        """Test using enum in a list."""
        types_list = [DrupalClassType.BLOCK, DrupalClassType.PLUGIN]
        assert DrupalClassType.BLOCK in types_list
        assert types_list.count(DrupalClassType.BLOCK) == 1

    def test_filter_with_list_comprehension(self):
        """Test filtering enum members with list comprehension."""
        plugin_related = [
            t for t in DrupalClassType
            if "plugin" in t.value or t in (DrupalClassType.BLOCK, DrupalClassType.FIELD_FORMATTER)
        ]
        assert DrupalClassType.PLUGIN in plugin_related
        assert DrupalClassType.BLOCK in plugin_related
        assert DrupalClassType.FIELD_FORMATTER in plugin_related


class TestDrupalClassTypeHashing:
    """Tests for enum hashing behavior."""

    def test_hashable(self):
        """Test enum members are hashable."""
        hash_value = hash(DrupalClassType.CONTROLLER)
        assert isinstance(hash_value, int)

    def test_consistent_hash(self):
        """Test same enum member has consistent hash."""
        hash1 = hash(DrupalClassType.SERVICE)
        hash2 = hash(DrupalClassType.SERVICE)
        assert hash1 == hash2

    def test_different_members_can_have_different_hash(self):
        """Test different members can be distinguished by hash (for set usage)."""
        # This test verifies enum can be used in sets
        members_set = {DrupalClassType.CONTROLLER, DrupalClassType.FORM}
        assert len(members_set) == 2


class TestDrupalClassTypePracticalScenarios:
    """Tests for practical usage scenarios in a Drupal context."""

    def test_check_if_class_is_plugin_type(self):
        """Test checking if a class type represents a plugin."""
        plugin_types = {
            DrupalClassType.PLUGIN,
            DrupalClassType.BLOCK,
            DrupalClassType.FIELD_FORMATTER,
            DrupalClassType.FIELD_WIDGET,
            DrupalClassType.QUEUE_WORKER,
            DrupalClassType.CONSTRAINT,
        }
        
        class_type = DrupalClassType.BLOCK
        assert class_type in plugin_types
        
        class_type = DrupalClassType.CONTROLLER
        assert class_type not in plugin_types

    def test_mapping_type_to_base_class(self):
        """Test mapping enum to Drupal base class names."""
        base_class_map = {
            DrupalClassType.CONTROLLER: "ControllerBase",
            DrupalClassType.FORM: "FormBase",
            DrupalClassType.BLOCK: "BlockBase",
            DrupalClassType.ENTITY: "ContentEntityBase",
        }
        
        assert base_class_map.get(DrupalClassType.CONTROLLER) == "ControllerBase"
        assert base_class_map.get(DrupalClassType.UNKNOWN) is None

    def test_default_to_unknown(self):
        """Test using UNKNOWN as default value."""
        detected_types = {"controller": DrupalClassType.CONTROLLER}
        
        # Simulate detecting a class type with fallback
        class_info = "some_unknown_pattern"
        result = detected_types.get(class_info, DrupalClassType.UNKNOWN)
        assert result == DrupalClassType.UNKNOWN

    def test_grouping_by_category(self):
        """Test grouping class types by category."""
        field_types = {DrupalClassType.FIELD_FORMATTER, DrupalClassType.FIELD_WIDGET}
        
        for field_type in field_types:
            assert "FIELD_" in field_type.name
