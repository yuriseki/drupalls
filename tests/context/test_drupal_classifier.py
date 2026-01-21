"""
Comprehensive tests for drupalls/context/drupal_classifier.py

Tests all public and private functions with:
- Classification by parent classes
- Classification by interfaces
- Classification by namespace patterns (fallback)
- Service class detection
- Edge cases and boundary conditions
"""
from __future__ import annotations

import pytest
from pathlib import Path

from drupalls.context.drupal_classifier import (
    DrupalContextClassifier,
    DRUPAL_BASE_CLASSES,
    DRUPAL_INTERFACES,
)
from drupalls.context.class_context import ClassContext
from drupalls.context.types import DrupalClassType


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def classifier() -> DrupalContextClassifier:
    """Create a fresh DrupalContextClassifier for each test."""
    return DrupalContextClassifier()


def make_context(
    fqcn: str = "Drupal\\test\\TestClass",
    short_name: str = "TestClass",
    parent_classes: list[str] | None = None,
    interfaces: list[str] | None = None,
    methods: list[str] | None = None,
    has_container_injection: bool = False,
    drupal_type: DrupalClassType = DrupalClassType.UNKNOWN,
) -> ClassContext:
    """Factory function to create ClassContext with minimal boilerplate."""
    return ClassContext(
        fqcn=fqcn,
        short_name=short_name,
        file_path=Path("/test.php"),
        class_line=10,
        parent_classes=parent_classes or [],
        interfaces=interfaces or [],
        methods=methods or [],
        has_container_injection=has_container_injection,
        drupal_type=drupal_type,
    )


# ============================================================================
# Tests for DrupalContextClassifier.classify()
# ============================================================================

class TestClassifyByParentClass:
    """Tests for classification based on parent classes."""

    def test_classify_controller_by_full_fqcn(self, classifier: DrupalContextClassifier):
        """Test classification of controller by fully qualified parent class."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Controller\\MyController",
            short_name="MyController",
            parent_classes=["Drupal\\Core\\Controller\\ControllerBase"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.CONTROLLER
        assert context.drupal_type == DrupalClassType.CONTROLLER

    def test_classify_controller_by_short_name(self, classifier: DrupalContextClassifier):
        """Test classification of controller by short parent class name."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Controller\\MyController",
            short_name="MyController",
            parent_classes=["ControllerBase"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.CONTROLLER

    def test_classify_form_formbase(self, classifier: DrupalContextClassifier):
        """Test classification of form extending FormBase."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Form\\MyForm",
            short_name="MyForm",
            parent_classes=["Drupal\\Core\\Form\\FormBase"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.FORM

    def test_classify_form_configformbase(self, classifier: DrupalContextClassifier):
        """Test classification of form extending ConfigFormBase."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Form\\SettingsForm",
            short_name="SettingsForm",
            parent_classes=["Drupal\\Core\\Form\\ConfigFormBase"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.FORM

    def test_classify_form_confirmformbase(self, classifier: DrupalContextClassifier):
        """Test classification of form extending ConfirmFormBase."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Form\\DeleteConfirmForm",
            short_name="DeleteConfirmForm",
            parent_classes=["Drupal\\Core\\Form\\ConfirmFormBase"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.FORM

    def test_classify_entity_content(self, classifier: DrupalContextClassifier):
        """Test classification of content entity."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Entity\\Article",
            short_name="Article",
            parent_classes=["Drupal\\Core\\Entity\\ContentEntityBase"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.ENTITY

    def test_classify_entity_config(self, classifier: DrupalContextClassifier):
        """Test classification of config entity."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Entity\\WorkflowType",
            short_name="WorkflowType",
            parent_classes=["Drupal\\Core\\Entity\\ConfigEntityBase"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.ENTITY

    def test_classify_plugin_core(self, classifier: DrupalContextClassifier):
        """Test classification of plugin extending Core PluginBase."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\MyPlugin",
            short_name="MyPlugin",
            parent_classes=["Drupal\\Core\\Plugin\\PluginBase"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.PLUGIN

    def test_classify_plugin_component(self, classifier: DrupalContextClassifier):
        """Test classification of plugin extending Component PluginBase."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\MyPlugin",
            short_name="MyPlugin",
            parent_classes=["Drupal\\Component\\Plugin\\PluginBase"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.PLUGIN

    def test_classify_block(self, classifier: DrupalContextClassifier):
        """Test classification of block plugin."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\Block\\MyBlock",
            short_name="MyBlock",
            parent_classes=["Drupal\\Core\\Block\\BlockBase"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.BLOCK

    def test_classify_field_formatter(self, classifier: DrupalContextClassifier):
        """Test classification of field formatter."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\Field\\Formatter\\MyFormatter",
            short_name="MyFormatter",
            parent_classes=["Drupal\\Core\\Field\\FormatterBase"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.FIELD_FORMATTER

    def test_classify_field_widget(self, classifier: DrupalContextClassifier):
        """Test classification of field widget."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\Field\\Widget\\MyWidget",
            short_name="MyWidget",
            parent_classes=["Drupal\\Core\\Field\\WidgetBase"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.FIELD_WIDGET

    def test_classify_migration_source(self, classifier: DrupalContextClassifier):
        """Test classification of migration source plugin."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\migrate\\source\\MySource",
            short_name="MySource",
            parent_classes=["Drupal\\migrate\\Plugin\\migrate\\source\\SourcePluginBase"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.MIGRATION

    def test_classify_migration_drupal_sql(self, classifier: DrupalContextClassifier):
        """Test classification of Drupal SQL migration source."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\migrate\\source\\D7Node",
            short_name="D7Node",
            parent_classes=["Drupal\\migrate_drupal\\Plugin\\migrate\\source\\DrupalSqlBase"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.MIGRATION

    def test_classify_queue_worker(self, classifier: DrupalContextClassifier):
        """Test classification of queue worker."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\QueueWorker\\MyQueueWorker",
            short_name="MyQueueWorker",
            parent_classes=["Drupal\\Core\\Queue\\QueueWorkerBase"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.QUEUE_WORKER

    def test_classify_constraint_symfony(self, classifier: DrupalContextClassifier):
        """Test classification of Symfony constraint."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\Validation\\Constraint\\MyConstraint",
            short_name="MyConstraint",
            parent_classes=["Symfony\\Component\\Validator\\Constraint"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.CONSTRAINT

    def test_classify_constraint_drupal(self, classifier: DrupalContextClassifier):
        """Test classification of Drupal constraint base."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\Validation\\Constraint\\MyConstraint",
            short_name="MyConstraint",
            parent_classes=["Drupal\\Core\\Validation\\Plugin\\Validation\\Constraint\\ConstraintBase"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.CONSTRAINT

    def test_classify_first_matching_parent_wins(self, classifier: DrupalContextClassifier):
        """Test that first matching parent class in list takes priority."""
        # Block extends PluginBase, but BlockBase should be checked first
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\Block\\MyBlock",
            short_name="MyBlock",
            parent_classes=[
                "Drupal\\Core\\Block\\BlockBase",  # More specific, should match
                "Drupal\\Core\\Plugin\\PluginBase",  # Less specific
            ],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.BLOCK

    def test_classify_parent_short_name_extraction(self, classifier: DrupalContextClassifier):
        """Test that short name is correctly extracted from full parent FQCN."""
        # Custom namespace with ControllerBase as short name
        context = make_context(
            fqcn="Drupal\\mymodule\\Controller\\MyController",
            short_name="MyController",
            parent_classes=["Custom\\Vendor\\Something\\ControllerBase"],
        )
        
        result = classifier.classify(context)
        
        # Should match the short name "ControllerBase" in DRUPAL_BASE_CLASSES
        assert result == DrupalClassType.CONTROLLER


class TestClassifyByInterface:
    """Tests for classification based on interfaces."""

    def test_classify_event_subscriber_full_fqcn(self, classifier: DrupalContextClassifier):
        """Test classification of event subscriber by full interface name."""
        context = make_context(
            fqcn="Drupal\\mymodule\\EventSubscriber\\MySubscriber",
            short_name="MySubscriber",
            interfaces=["Symfony\\Component\\EventDispatcher\\EventSubscriberInterface"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.EVENT_SUBSCRIBER
        assert context.drupal_type == DrupalClassType.EVENT_SUBSCRIBER

    def test_classify_event_subscriber_short_name(self, classifier: DrupalContextClassifier):
        """Test classification of event subscriber by short interface name."""
        context = make_context(
            fqcn="Drupal\\mymodule\\EventSubscriber\\MySubscriber",
            short_name="MySubscriber",
            interfaces=["EventSubscriberInterface"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.EVENT_SUBSCRIBER

    def test_classify_access_checker(self, classifier: DrupalContextClassifier):
        """Test classification of access checker."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Access\\MyAccessChecker",
            short_name="MyAccessChecker",
            interfaces=["Drupal\\Core\\Routing\\Access\\AccessInterface"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.ACCESS_CHECKER

    def test_classify_form_by_interface(self, classifier: DrupalContextClassifier):
        """Test classification of form by FormInterface."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Form\\CustomForm",
            short_name="CustomForm",
            interfaces=["Drupal\\Core\\Form\\FormInterface"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.FORM

    def test_classify_entity_by_interface(self, classifier: DrupalContextClassifier):
        """Test classification of entity by EntityInterface."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Entity\\CustomEntity",
            short_name="CustomEntity",
            interfaces=["Drupal\\Core\\Entity\\EntityInterface"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.ENTITY

    def test_classify_block_by_interface(self, classifier: DrupalContextClassifier):
        """Test classification of block by BlockPluginInterface."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\Block\\MyBlock",
            short_name="MyBlock",
            interfaces=["Drupal\\Core\\Block\\BlockPluginInterface"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.BLOCK

    def test_classify_parent_takes_priority_over_interface(self, classifier: DrupalContextClassifier):
        """Test that parent class classification takes priority over interface."""
        # Entity that also implements FormInterface
        context = make_context(
            fqcn="Drupal\\mymodule\\Entity\\FormableEntity",
            short_name="FormableEntity",
            parent_classes=["Drupal\\Core\\Entity\\ContentEntityBase"],
            interfaces=["Drupal\\Core\\Form\\FormInterface"],
        )
        
        result = classifier.classify(context)
        
        # Parent class should win
        assert result == DrupalClassType.ENTITY

    def test_classify_interface_short_name_extraction(self, classifier: DrupalContextClassifier):
        """Test that short name is correctly extracted from interface FQCN."""
        context = make_context(
            fqcn="Drupal\\mymodule\\EventSubscriber\\Custom",
            short_name="Custom",
            interfaces=["My\\Custom\\Namespace\\EventSubscriberInterface"],
        )
        
        result = classifier.classify(context)
        
        # Should match short name "EventSubscriberInterface"
        assert result == DrupalClassType.EVENT_SUBSCRIBER


class TestClassifyByNamespace:
    """Tests for classification based on namespace patterns (fallback)."""

    def test_classify_controller_by_namespace(self, classifier: DrupalContextClassifier):
        """Test classification by \\Controller\\ namespace pattern."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Controller\\ArticleController",
            short_name="ArticleController",
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.CONTROLLER

    def test_classify_form_by_namespace(self, classifier: DrupalContextClassifier):
        """Test classification by \\Form\\ namespace pattern."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Form\\SettingsForm",
            short_name="SettingsForm",
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.FORM

    def test_classify_block_by_namespace(self, classifier: DrupalContextClassifier):
        """Test classification by \\Plugin\\Block\\ namespace pattern."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\Block\\FeaturedBlock",
            short_name="FeaturedBlock",
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.BLOCK

    def test_classify_field_formatter_by_namespace(self, classifier: DrupalContextClassifier):
        """Test classification by \\Plugin\\Field\\Formatter\\ namespace."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\Field\\Formatter\\CustomFormatter",
            short_name="CustomFormatter",
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.FIELD_FORMATTER

    def test_classify_field_widget_by_namespace(self, classifier: DrupalContextClassifier):
        """Test classification by \\Plugin\\Field\\Widget\\ namespace."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\Field\\Widget\\CustomWidget",
            short_name="CustomWidget",
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.FIELD_WIDGET

    def test_classify_migration_by_namespace(self, classifier: DrupalContextClassifier):
        """Test classification by \\Plugin\\migrate\\ namespace."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\migrate\\source\\Users",
            short_name="Users",
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.MIGRATION

    def test_classify_queue_worker_by_namespace(self, classifier: DrupalContextClassifier):
        """Test classification by \\Plugin\\QueueWorker\\ namespace."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\QueueWorker\\EmailSender",
            short_name="EmailSender",
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.QUEUE_WORKER

    def test_classify_plugin_by_namespace(self, classifier: DrupalContextClassifier):
        """Test classification by generic \\Plugin\\ namespace."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\Action\\PublishNode",
            short_name="PublishNode",
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.PLUGIN

    def test_classify_entity_by_namespace(self, classifier: DrupalContextClassifier):
        """Test classification by \\Entity\\ namespace."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Entity\\Article",
            short_name="Article",
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.ENTITY

    def test_classify_event_subscriber_by_namespace(self, classifier: DrupalContextClassifier):
        """Test classification by \\EventSubscriber\\ namespace."""
        context = make_context(
            fqcn="Drupal\\mymodule\\EventSubscriber\\CacheSubscriber",
            short_name="CacheSubscriber",
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.EVENT_SUBSCRIBER

    def test_classify_access_by_namespace(self, classifier: DrupalContextClassifier):
        """Test classification by \\Access\\ namespace."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Access\\CustomAccessChecker",
            short_name="CustomAccessChecker",
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.ACCESS_CHECKER

    def test_namespace_classification_case_insensitive(self, classifier: DrupalContextClassifier):
        """Test that namespace classification is case-insensitive."""
        context = make_context(
            fqcn="Drupal\\mymodule\\CONTROLLER\\MyController",
            short_name="MyController",
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.CONTROLLER

    def test_namespace_block_takes_priority_over_plugin(self, classifier: DrupalContextClassifier):
        """Test that \\Plugin\\Block\\ is matched before generic \\Plugin\\."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\Block\\TestBlock",
            short_name="TestBlock",
        )
        
        result = classifier.classify(context)
        
        # Block should be matched, not generic plugin
        assert result == DrupalClassType.BLOCK

    def test_namespace_field_formatter_takes_priority_over_plugin(self, classifier: DrupalContextClassifier):
        """Test that \\Plugin\\Field\\Formatter\\ is matched before generic \\Plugin\\."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Plugin\\Field\\Formatter\\TestFormatter",
            short_name="TestFormatter",
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.FIELD_FORMATTER


class TestClassifyUnknown:
    """Tests for classification returning UNKNOWN."""

    def test_classify_unknown_when_no_match(self, classifier: DrupalContextClassifier):
        """Test that UNKNOWN is returned when nothing matches."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Utility\\Helper",
            short_name="Helper",
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.UNKNOWN
        assert context.drupal_type == DrupalClassType.UNKNOWN

    def test_classify_unknown_non_drupal_namespace(self, classifier: DrupalContextClassifier):
        """Test classification of non-Drupal namespace."""
        context = make_context(
            fqcn="Vendor\\Library\\SomeClass",
            short_name="SomeClass",
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.UNKNOWN


class TestClassifyEdgeCases:
    """Tests for edge cases in classification."""

    def test_classify_empty_parent_classes(self, classifier: DrupalContextClassifier):
        """Test classification with empty parent_classes list."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Controller\\MyController",
            short_name="MyController",
            parent_classes=[],
        )
        
        result = classifier.classify(context)
        
        # Should fall back to namespace matching
        assert result == DrupalClassType.CONTROLLER

    def test_classify_empty_interfaces(self, classifier: DrupalContextClassifier):
        """Test classification with empty interfaces list."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Form\\MyForm",
            short_name="MyForm",
            interfaces=[],
        )
        
        result = classifier.classify(context)
        
        # Should fall back to namespace matching
        assert result == DrupalClassType.FORM

    def test_classify_empty_fqcn(self, classifier: DrupalContextClassifier):
        """Test classification with empty FQCN."""
        context = make_context(
            fqcn="",
            short_name="",
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.UNKNOWN

    def test_classify_updates_context_drupal_type(self, classifier: DrupalContextClassifier):
        """Test that classify() updates context.drupal_type."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Controller\\MyController",
            short_name="MyController",
            parent_classes=["ControllerBase"],
            drupal_type=DrupalClassType.UNKNOWN,
        )
        
        # Before classification
        assert context.drupal_type == DrupalClassType.UNKNOWN
        
        result = classifier.classify(context)
        
        # After classification - both return and context should be updated
        assert result == DrupalClassType.CONTROLLER
        assert context.drupal_type == DrupalClassType.CONTROLLER

    def test_classify_preserves_existing_type_if_match_found(self, classifier: DrupalContextClassifier):
        """Test that classify overwrites any existing drupal_type."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Controller\\MyController",
            short_name="MyController",
            parent_classes=["ControllerBase"],
            drupal_type=DrupalClassType.FORM,  # Pre-set to wrong type
        )
        
        result = classifier.classify(context)
        
        # Should overwrite the pre-set type
        assert result == DrupalClassType.CONTROLLER
        assert context.drupal_type == DrupalClassType.CONTROLLER

    def test_classify_multiple_unrecognized_parents(self, classifier: DrupalContextClassifier):
        """Test classification with multiple unrecognized parent classes."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Service\\MyService",
            short_name="MyService",
            parent_classes=["Custom\\Base\\AbstractBase", "Another\\UnknownClass"],
        )
        
        result = classifier.classify(context)
        
        # No parent matches, no interface matches, no namespace match
        assert result == DrupalClassType.UNKNOWN

    def test_classify_multiple_unrecognized_interfaces(self, classifier: DrupalContextClassifier):
        """Test classification with multiple unrecognized interfaces."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Service\\MyService",
            short_name="MyService",
            interfaces=["Custom\\MyInterface", "Another\\OtherInterface"],
        )
        
        result = classifier.classify(context)
        
        assert result == DrupalClassType.UNKNOWN


# ============================================================================
# Tests for DrupalContextClassifier.is_service_class()
# ============================================================================

class TestIsServiceClass:
    """Tests for is_service_class method."""

    def test_is_service_with_container_injection(self, classifier: DrupalContextClassifier):
        """Test that has_container_injection=True indicates a service."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Service\\MyService",
            short_name="MyService",
            has_container_injection=True,
        )
        
        result = classifier.is_service_class(context)
        
        assert result is True

    def test_is_service_with_create_method(self, classifier: DrupalContextClassifier):
        """Test that having a create() method indicates a service."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Service\\MyService",
            short_name="MyService",
            methods=["__construct", "create", "doSomething"],
        )
        
        result = classifier.is_service_class(context)
        
        assert result is True

    def test_is_service_event_subscriber_type(self, classifier: DrupalContextClassifier):
        """Test that EVENT_SUBSCRIBER type is always a service."""
        context = make_context(
            fqcn="Drupal\\mymodule\\EventSubscriber\\MySubscriber",
            short_name="MySubscriber",
            drupal_type=DrupalClassType.EVENT_SUBSCRIBER,
        )
        
        result = classifier.is_service_class(context)
        
        assert result is True

    def test_is_service_access_checker_type(self, classifier: DrupalContextClassifier):
        """Test that ACCESS_CHECKER type is always a service."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Access\\MyAccessChecker",
            short_name="MyAccessChecker",
            drupal_type=DrupalClassType.ACCESS_CHECKER,
        )
        
        result = classifier.is_service_class(context)
        
        assert result is True

    def test_is_not_service_unknown_type_no_indicators(self, classifier: DrupalContextClassifier):
        """Test that class without indicators is not a service."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Utility\\Helper",
            short_name="Helper",
            drupal_type=DrupalClassType.UNKNOWN,
            has_container_injection=False,
            methods=["helperMethod"],
        )
        
        result = classifier.is_service_class(context)
        
        assert result is False

    def test_is_not_service_controller_without_injection(self, classifier: DrupalContextClassifier):
        """Test that controller without container injection is not flagged as service."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Controller\\SimpleController",
            short_name="SimpleController",
            drupal_type=DrupalClassType.CONTROLLER,
            has_container_injection=False,
            methods=["index"],  # No create() method
        )
        
        result = classifier.is_service_class(context)
        
        assert result is False

    def test_is_service_controller_with_injection(self, classifier: DrupalContextClassifier):
        """Test that controller with container injection is a service."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Controller\\ServiceController",
            short_name="ServiceController",
            drupal_type=DrupalClassType.CONTROLLER,
            has_container_injection=True,
        )
        
        result = classifier.is_service_class(context)
        
        assert result is True

    def test_is_service_empty_methods(self, classifier: DrupalContextClassifier):
        """Test service detection with empty methods list."""
        context = make_context(
            fqcn="Drupal\\mymodule\\Service\\MyService",
            short_name="MyService",
            methods=[],
            has_container_injection=False,
        )
        
        result = classifier.is_service_class(context)
        
        assert result is False

    def test_is_service_plugin_types_not_service_by_default(self, classifier: DrupalContextClassifier):
        """Test that plugin types are not considered services by default."""
        for dtype in [DrupalClassType.PLUGIN, DrupalClassType.BLOCK, DrupalClassType.FIELD_FORMATTER]:
            context = make_context(
                fqcn="Drupal\\mymodule\\Plugin\\SomePlugin",
                short_name="SomePlugin",
                drupal_type=dtype,
                has_container_injection=False,
                methods=["build"],
            )
            
            result = classifier.is_service_class(context)
            
            assert result is False, f"Expected {dtype} to not be a service by default"


# ============================================================================
# Tests for _classify_by_namespace()
# ============================================================================

class TestClassifyByNamespacePrivate:
    """Tests for _classify_by_namespace private method."""

    def test_classify_by_namespace_controller(self, classifier: DrupalContextClassifier):
        """Test _classify_by_namespace with controller pattern."""
        result = classifier._classify_by_namespace("Drupal\\mymodule\\Controller\\Test")
        
        assert result == DrupalClassType.CONTROLLER

    def test_classify_by_namespace_case_insensitive(self, classifier: DrupalContextClassifier):
        """Test that _classify_by_namespace is case-insensitive."""
        result = classifier._classify_by_namespace("Drupal\\mymodule\\CONTROLLER\\Test")
        
        assert result == DrupalClassType.CONTROLLER

    def test_classify_by_namespace_no_match(self, classifier: DrupalContextClassifier):
        """Test _classify_by_namespace returns UNKNOWN when no pattern matches."""
        result = classifier._classify_by_namespace("Drupal\\mymodule\\Utility\\Helper")
        
        assert result == DrupalClassType.UNKNOWN

    def test_classify_by_namespace_empty_string(self, classifier: DrupalContextClassifier):
        """Test _classify_by_namespace with empty string."""
        result = classifier._classify_by_namespace("")
        
        assert result == DrupalClassType.UNKNOWN

    def test_classify_by_namespace_multiple_patterns(self, classifier: DrupalContextClassifier):
        """Test _classify_by_namespace with multiple matching patterns."""
        # This FQCN contains both \\Plugin\\ and \\Block\\
        # The more specific \\plugin\\block\\ should match first based on dict order
        result = classifier._classify_by_namespace("Drupal\\mymodule\\Plugin\\Block\\Test")
        
        assert result == DrupalClassType.BLOCK


# ============================================================================
# Tests for module-level constants
# ============================================================================

class TestDrupalBaseClasses:
    """Tests for DRUPAL_BASE_CLASSES constant."""

    def test_drupal_base_classes_is_dict(self):
        """Test that DRUPAL_BASE_CLASSES is a dict."""
        assert isinstance(DRUPAL_BASE_CLASSES, dict)

    def test_drupal_base_classes_contains_controller(self):
        """Test that DRUPAL_BASE_CLASSES contains controller mappings."""
        assert "Drupal\\Core\\Controller\\ControllerBase" in DRUPAL_BASE_CLASSES
        assert "ControllerBase" in DRUPAL_BASE_CLASSES
        assert DRUPAL_BASE_CLASSES["ControllerBase"] == DrupalClassType.CONTROLLER

    def test_drupal_base_classes_contains_forms(self):
        """Test that DRUPAL_BASE_CLASSES contains form mappings."""
        assert "FormBase" in DRUPAL_BASE_CLASSES
        assert "ConfigFormBase" in DRUPAL_BASE_CLASSES
        assert DRUPAL_BASE_CLASSES["FormBase"] == DrupalClassType.FORM

    def test_drupal_base_classes_values_are_drupal_class_type(self):
        """Test that all values in DRUPAL_BASE_CLASSES are DrupalClassType."""
        for key, value in DRUPAL_BASE_CLASSES.items():
            assert isinstance(value, DrupalClassType), f"Value for {key} is not DrupalClassType"


class TestDrupalInterfaces:
    """Tests for DRUPAL_INTERFACES constant."""

    def test_drupal_interfaces_is_dict(self):
        """Test that DRUPAL_INTERFACES is a dict."""
        assert isinstance(DRUPAL_INTERFACES, dict)

    def test_drupal_interfaces_contains_event_subscriber(self):
        """Test that DRUPAL_INTERFACES contains event subscriber."""
        assert "Symfony\\Component\\EventDispatcher\\EventSubscriberInterface" in DRUPAL_INTERFACES
        assert "EventSubscriberInterface" in DRUPAL_INTERFACES
        assert DRUPAL_INTERFACES["EventSubscriberInterface"] == DrupalClassType.EVENT_SUBSCRIBER

    def test_drupal_interfaces_contains_access_interface(self):
        """Test that DRUPAL_INTERFACES contains access interface."""
        assert "AccessInterface" in DRUPAL_INTERFACES
        assert DRUPAL_INTERFACES["AccessInterface"] == DrupalClassType.ACCESS_CHECKER

    def test_drupal_interfaces_values_are_drupal_class_type(self):
        """Test that all values in DRUPAL_INTERFACES are DrupalClassType."""
        for key, value in DRUPAL_INTERFACES.items():
            assert isinstance(value, DrupalClassType), f"Value for {key} is not DrupalClassType"


# ============================================================================
# Integration tests
# ============================================================================

class TestClassifierIntegration:
    """Integration tests for typical classification scenarios."""

    def test_full_block_plugin_classification(self, classifier: DrupalContextClassifier):
        """Test classifying a complete block plugin with all info."""
        context = ClassContext(
            fqcn="Drupal\\mymodule\\Plugin\\Block\\FeaturedContentBlock",
            short_name="FeaturedContentBlock",
            file_path=Path("/var/www/drupal/web/modules/mymodule/src/Plugin/Block/FeaturedContentBlock.php"),
            class_line=20,
            parent_classes=[
                "Drupal\\Core\\Block\\BlockBase",
                "Drupal\\Core\\Plugin\\PluginBase",
            ],
            interfaces=[
                "Drupal\\Core\\Block\\BlockPluginInterface",
                "Drupal\\Core\\Plugin\\ContainerFactoryPluginInterface",
            ],
            has_container_injection=True,
            methods=["build", "blockForm", "blockSubmit", "create"],
        )
        
        result = classifier.classify(context)
        is_service = classifier.is_service_class(context)
        
        assert result == DrupalClassType.BLOCK
        assert context.drupal_type == DrupalClassType.BLOCK
        assert is_service is True  # has_container_injection is True

    def test_full_event_subscriber_classification(self, classifier: DrupalContextClassifier):
        """Test classifying a complete event subscriber."""
        context = ClassContext(
            fqcn="Drupal\\mymodule\\EventSubscriber\\RequestSubscriber",
            short_name="RequestSubscriber",
            file_path=Path("/var/www/drupal/web/modules/mymodule/src/EventSubscriber/RequestSubscriber.php"),
            class_line=10,
            parent_classes=[],
            interfaces=["Symfony\\Component\\EventDispatcher\\EventSubscriberInterface"],
            has_container_injection=False,
            methods=["getSubscribedEvents", "onRequest"],
        )
        
        result = classifier.classify(context)
        is_service = classifier.is_service_class(context)
        
        assert result == DrupalClassType.EVENT_SUBSCRIBER
        assert is_service is True  # EVENT_SUBSCRIBER is always a service

    def test_classify_then_is_service_workflow(self, classifier: DrupalContextClassifier):
        """Test typical workflow: classify first, then check is_service."""
        context = make_context(
            fqcn="Drupal\\mymodule\\EventSubscriber\\CacheSubscriber",
            short_name="CacheSubscriber",
            interfaces=["EventSubscriberInterface"],
        )
        
        # First classify
        classifier.classify(context)
        
        # Then check if it's a service
        is_service = classifier.is_service_class(context)
        
        assert context.drupal_type == DrupalClassType.EVENT_SUBSCRIBER
        assert is_service is True

    def test_multiple_classifications_on_same_classifier(self, classifier: DrupalContextClassifier):
        """Test that classifier can be reused for multiple contexts."""
        contexts = [
            make_context(
                fqcn="Drupal\\mod\\Controller\\A",
                parent_classes=["ControllerBase"],
            ),
            make_context(
                fqcn="Drupal\\mod\\Form\\B",
                parent_classes=["FormBase"],
            ),
            make_context(
                fqcn="Drupal\\mod\\Plugin\\Block\\C",
                parent_classes=["BlockBase"],
            ),
        ]
        
        expected = [
            DrupalClassType.CONTROLLER,
            DrupalClassType.FORM,
            DrupalClassType.BLOCK,
        ]
        
        for context, expected_type in zip(contexts, expected):
            result = classifier.classify(context)
            assert result == expected_type
