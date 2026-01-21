"""
Comprehensive tests for drupalls/context/class_context.py

Tests all public and private functions with:
- Dataclass creation with all fields
- Default values (especially default_factory for list fields)
- Edge cases (empty values, boundary conditions)
- Method behavior (has_parent, implements_interface, has_method)
"""
from __future__ import annotations

import pytest
from pathlib import Path

from drupalls.context.class_context import ClassContext
from drupalls.context.types import DrupalClassType


class TestClassContextCreation:
    """Tests for ClassContext dataclass instantiation."""

    def test_create_with_required_fields_only(self):
        """Test creating ClassContext with only required fields."""
        ctx = ClassContext(
            fqcn="Drupal\\mymodule\\Controller\\MyController",
            short_name="MyController",
            file_path=Path("/var/www/drupal/web/modules/mymodule/src/Controller/MyController.php"),
            class_line=10,
        )
        
        assert ctx.fqcn == "Drupal\\mymodule\\Controller\\MyController"
        assert ctx.short_name == "MyController"
        assert ctx.file_path == Path("/var/www/drupal/web/modules/mymodule/src/Controller/MyController.php")
        assert ctx.class_line == 10

    def test_default_values_for_list_fields(self):
        """Test that list fields have empty lists as defaults."""
        ctx = ClassContext(
            fqcn="Drupal\\test\\TestClass",
            short_name="TestClass",
            file_path=Path("/test.php"),
            class_line=0,
        )
        
        # All list fields should be empty lists (not None)
        assert ctx.parent_classes == []
        assert ctx.interfaces == []
        assert ctx.traits == []
        assert ctx.methods == []
        assert ctx.properties == []
        
        # Verify they are independent instances (not shared)
        assert ctx.parent_classes is not ctx.interfaces
        assert ctx.methods is not ctx.properties

    def test_default_value_for_drupal_type(self):
        """Test that drupal_type defaults to UNKNOWN."""
        ctx = ClassContext(
            fqcn="Drupal\\test\\TestClass",
            short_name="TestClass",
            file_path=Path("/test.php"),
            class_line=0,
        )
        
        assert ctx.drupal_type == DrupalClassType.UNKNOWN

    def test_default_value_for_has_container_injection(self):
        """Test that has_container_injection defaults to False."""
        ctx = ClassContext(
            fqcn="Drupal\\test\\TestClass",
            short_name="TestClass",
            file_path=Path("/test.php"),
            class_line=0,
        )
        
        assert ctx.has_container_injection is False

    def test_create_with_all_fields(self):
        """Test creating ClassContext with all fields specified."""
        ctx = ClassContext(
            fqcn="Drupal\\mymodule\\Plugin\\Block\\MyBlock",
            short_name="MyBlock",
            file_path=Path("/var/www/drupal/web/modules/mymodule/src/Plugin/Block/MyBlock.php"),
            class_line=15,
            parent_classes=["Drupal\\Core\\Block\\BlockBase", "Drupal\\Core\\Plugin\\PluginBase"],
            interfaces=["Drupal\\Core\\Block\\BlockPluginInterface"],
            traits=["Drupal\\Core\\StringTranslation\\StringTranslationTrait"],
            drupal_type=DrupalClassType.BLOCK,
            has_container_injection=True,
            methods=["build", "blockForm", "blockSubmit"],
            properties=["configuration", "pluginId"],
        )
        
        assert ctx.fqcn == "Drupal\\mymodule\\Plugin\\Block\\MyBlock"
        assert ctx.short_name == "MyBlock"
        assert ctx.class_line == 15
        assert len(ctx.parent_classes) == 2
        assert "Drupal\\Core\\Block\\BlockBase" in ctx.parent_classes
        assert len(ctx.interfaces) == 1
        assert len(ctx.traits) == 1
        assert ctx.drupal_type == DrupalClassType.BLOCK
        assert ctx.has_container_injection is True
        assert len(ctx.methods) == 3
        assert len(ctx.properties) == 2

    def test_list_fields_are_mutable(self):
        """Test that list fields can be modified after creation."""
        ctx = ClassContext(
            fqcn="Drupal\\test\\TestClass",
            short_name="TestClass",
            file_path=Path("/test.php"),
            class_line=0,
        )
        
        # Should be able to append to list fields
        ctx.methods.append("newMethod")
        ctx.properties.append("newProperty")
        ctx.parent_classes.append("SomeParent")
        
        assert "newMethod" in ctx.methods
        assert "newProperty" in ctx.properties
        assert "SomeParent" in ctx.parent_classes

    def test_list_fields_independence_between_instances(self):
        """Test that list fields are not shared between instances."""
        ctx1 = ClassContext(
            fqcn="Drupal\\test\\TestClass1",
            short_name="TestClass1",
            file_path=Path("/test1.php"),
            class_line=0,
        )
        ctx2 = ClassContext(
            fqcn="Drupal\\test\\TestClass2",
            short_name="TestClass2",
            file_path=Path("/test2.php"),
            class_line=0,
        )
        
        # Modify ctx1's lists
        ctx1.methods.append("method1")
        ctx1.parent_classes.append("Parent1")
        
        # ctx2 should be unaffected
        assert ctx2.methods == []
        assert ctx2.parent_classes == []


class TestClassContextEdgeCases:
    """Tests for edge cases in ClassContext."""

    def test_empty_fqcn(self):
        """Test ClassContext with empty fqcn string."""
        ctx = ClassContext(
            fqcn="",
            short_name="",
            file_path=Path("/test.php"),
            class_line=0,
        )
        
        assert ctx.fqcn == ""
        assert ctx.short_name == ""

    def test_class_line_zero(self):
        """Test ClassContext with class_line at 0 (first line)."""
        ctx = ClassContext(
            fqcn="Drupal\\test\\TestClass",
            short_name="TestClass",
            file_path=Path("/test.php"),
            class_line=0,
        )
        
        assert ctx.class_line == 0

    def test_class_line_large_value(self):
        """Test ClassContext with large class_line value."""
        ctx = ClassContext(
            fqcn="Drupal\\test\\TestClass",
            short_name="TestClass",
            file_path=Path("/test.php"),
            class_line=999999,
        )
        
        assert ctx.class_line == 999999

    def test_path_with_special_characters(self):
        """Test ClassContext with path containing special characters."""
        special_path = Path("/var/www/drupal-10/web/modules/my_module/src/Test Class.php")
        ctx = ClassContext(
            fqcn="Drupal\\my_module\\Test",
            short_name="Test",
            file_path=special_path,
            class_line=5,
        )
        
        assert ctx.file_path == special_path

    def test_fqcn_with_many_namespace_levels(self):
        """Test ClassContext with deeply nested namespace."""
        deep_fqcn = "Drupal\\module\\Sub1\\Sub2\\Sub3\\Sub4\\DeepClass"
        ctx = ClassContext(
            fqcn=deep_fqcn,
            short_name="DeepClass",
            file_path=Path("/test.php"),
            class_line=0,
        )
        
        assert ctx.fqcn == deep_fqcn

    def test_all_drupal_class_types(self):
        """Test ClassContext with each DrupalClassType value."""
        for drupal_type in DrupalClassType:
            ctx = ClassContext(
                fqcn="Drupal\\test\\TestClass",
                short_name="TestClass",
                file_path=Path("/test.php"),
                class_line=0,
                drupal_type=drupal_type,
            )
            assert ctx.drupal_type == drupal_type


class TestHasParent:
    """Tests for ClassContext.has_parent method."""

    @pytest.fixture
    def controller_context(self) -> ClassContext:
        """Create a ClassContext for a controller with parent classes."""
        return ClassContext(
            fqcn="Drupal\\mymodule\\Controller\\MyController",
            short_name="MyController",
            file_path=Path("/test.php"),
            class_line=10,
            parent_classes=[
                "Drupal\\Core\\Controller\\ControllerBase",
                "Drupal\\Core\\DependencyInjection\\ContainerInjectionInterface",
            ],
        )

    def test_has_parent_exact_match(self, controller_context: ClassContext):
        """Test has_parent with exact case match."""
        assert controller_context.has_parent("Drupal\\Core\\Controller\\ControllerBase") is True

    def test_has_parent_case_insensitive(self, controller_context: ClassContext):
        """Test has_parent is case-insensitive."""
        assert controller_context.has_parent("drupal\\core\\controller\\controllerbase") is True
        assert controller_context.has_parent("DRUPAL\\CORE\\CONTROLLER\\CONTROLLERBASE") is True
        assert controller_context.has_parent("Drupal\\CORE\\Controller\\controllerBase") is True

    def test_has_parent_not_found(self, controller_context: ClassContext):
        """Test has_parent returns False when parent not in list."""
        assert controller_context.has_parent("Drupal\\Core\\Form\\FormBase") is False
        assert controller_context.has_parent("NonExistent\\Class") is False

    def test_has_parent_empty_list(self):
        """Test has_parent with empty parent_classes list."""
        ctx = ClassContext(
            fqcn="Drupal\\test\\TestClass",
            short_name="TestClass",
            file_path=Path("/test.php"),
            class_line=0,
            parent_classes=[],
        )
        
        assert ctx.has_parent("AnyClass") is False

    def test_has_parent_partial_match_not_found(self, controller_context: ClassContext):
        """Test has_parent does not match partial strings."""
        # Partial match should NOT work
        assert controller_context.has_parent("ControllerBase") is False
        assert controller_context.has_parent("Drupal\\Core\\Controller") is False

    def test_has_parent_with_empty_string(self, controller_context: ClassContext):
        """Test has_parent with empty string argument."""
        assert controller_context.has_parent("") is False


class TestImplementsInterface:
    """Tests for ClassContext.implements_interface method."""

    @pytest.fixture
    def service_context(self) -> ClassContext:
        """Create a ClassContext for a service with interfaces."""
        return ClassContext(
            fqcn="Drupal\\mymodule\\Service\\MyService",
            short_name="MyService",
            file_path=Path("/test.php"),
            class_line=5,
            interfaces=[
                "Drupal\\mymodule\\MyServiceInterface",
                "Drupal\\Core\\Cache\\CacheableDependencyInterface",
            ],
        )

    def test_implements_interface_exact_match(self, service_context: ClassContext):
        """Test implements_interface with exact case match."""
        assert service_context.implements_interface("Drupal\\mymodule\\MyServiceInterface") is True

    def test_implements_interface_case_insensitive(self, service_context: ClassContext):
        """Test implements_interface is case-insensitive."""
        assert service_context.implements_interface("drupal\\mymodule\\myserviceinterface") is True
        assert service_context.implements_interface("DRUPAL\\MYMODULE\\MYSERVICEINTERFACE") is True

    def test_implements_interface_not_found(self, service_context: ClassContext):
        """Test implements_interface returns False when interface not in list."""
        assert service_context.implements_interface("Drupal\\Other\\OtherInterface") is False
        assert service_context.implements_interface("NonExistent\\Interface") is False

    def test_implements_interface_empty_list(self):
        """Test implements_interface with empty interfaces list."""
        ctx = ClassContext(
            fqcn="Drupal\\test\\TestClass",
            short_name="TestClass",
            file_path=Path("/test.php"),
            class_line=0,
            interfaces=[],
        )
        
        assert ctx.implements_interface("AnyInterface") is False

    def test_implements_interface_partial_match_not_found(self, service_context: ClassContext):
        """Test implements_interface does not match partial strings."""
        assert service_context.implements_interface("MyServiceInterface") is False
        assert service_context.implements_interface("Drupal\\mymodule") is False

    def test_implements_interface_with_empty_string(self, service_context: ClassContext):
        """Test implements_interface with empty string argument."""
        assert service_context.implements_interface("") is False


class TestHasMethod:
    """Tests for ClassContext.has_method method."""

    @pytest.fixture
    def class_with_methods(self) -> ClassContext:
        """Create a ClassContext with methods defined."""
        return ClassContext(
            fqcn="Drupal\\mymodule\\MyClass",
            short_name="MyClass",
            file_path=Path("/test.php"),
            class_line=0,
            methods=["__construct", "build", "getConfiguration", "setConfiguration"],
        )

    def test_has_method_found(self, class_with_methods: ClassContext):
        """Test has_method returns True for existing method."""
        assert class_with_methods.has_method("build") is True
        assert class_with_methods.has_method("__construct") is True
        assert class_with_methods.has_method("getConfiguration") is True

    def test_has_method_not_found(self, class_with_methods: ClassContext):
        """Test has_method returns False for non-existing method."""
        assert class_with_methods.has_method("nonExistent") is False
        assert class_with_methods.has_method("render") is False

    def test_has_method_case_sensitive(self, class_with_methods: ClassContext):
        """Test has_method is case-sensitive (unlike has_parent/implements_interface)."""
        # PHP method names are case-insensitive, but our list stores exact names
        # The implementation uses exact match, so this tests current behavior
        assert class_with_methods.has_method("Build") is False
        assert class_with_methods.has_method("BUILD") is False
        assert class_with_methods.has_method("build") is True

    def test_has_method_empty_list(self):
        """Test has_method with empty methods list."""
        ctx = ClassContext(
            fqcn="Drupal\\test\\TestClass",
            short_name="TestClass",
            file_path=Path("/test.php"),
            class_line=0,
            methods=[],
        )
        
        assert ctx.has_method("anyMethod") is False

    def test_has_method_with_empty_string(self, class_with_methods: ClassContext):
        """Test has_method with empty string argument."""
        assert class_with_methods.has_method("") is False

    def test_has_method_special_method_names(self):
        """Test has_method with PHP magic methods."""
        ctx = ClassContext(
            fqcn="Drupal\\test\\TestClass",
            short_name="TestClass",
            file_path=Path("/test.php"),
            class_line=0,
            methods=["__construct", "__destruct", "__toString", "__get", "__set"],
        )
        
        assert ctx.has_method("__construct") is True
        assert ctx.has_method("__toString") is True
        assert ctx.has_method("__clone") is False


class TestClassContextDataclassBehavior:
    """Tests for dataclass-specific behavior."""

    def test_equality(self):
        """Test that two ClassContext instances with same values are equal."""
        ctx1 = ClassContext(
            fqcn="Drupal\\test\\TestClass",
            short_name="TestClass",
            file_path=Path("/test.php"),
            class_line=10,
            parent_classes=["Parent"],
            interfaces=["Interface"],
            drupal_type=DrupalClassType.SERVICE,
        )
        ctx2 = ClassContext(
            fqcn="Drupal\\test\\TestClass",
            short_name="TestClass",
            file_path=Path("/test.php"),
            class_line=10,
            parent_classes=["Parent"],
            interfaces=["Interface"],
            drupal_type=DrupalClassType.SERVICE,
        )
        
        assert ctx1 == ctx2

    def test_inequality_different_fqcn(self):
        """Test that ClassContext instances with different fqcn are not equal."""
        ctx1 = ClassContext(
            fqcn="Drupal\\test\\TestClass1",
            short_name="TestClass1",
            file_path=Path("/test.php"),
            class_line=10,
        )
        ctx2 = ClassContext(
            fqcn="Drupal\\test\\TestClass2",
            short_name="TestClass2",
            file_path=Path("/test.php"),
            class_line=10,
        )
        
        assert ctx1 != ctx2

    def test_repr(self):
        """Test that ClassContext has a useful string representation."""
        ctx = ClassContext(
            fqcn="Drupal\\test\\TestClass",
            short_name="TestClass",
            file_path=Path("/test.php"),
            class_line=10,
        )
        
        repr_str = repr(ctx)
        assert "ClassContext" in repr_str
        # In repr, backslashes are escaped, so we check for the escaped version
        assert "Drupal\\\\test\\\\TestClass" in repr_str
        assert "TestClass" in repr_str


class TestClassContextIntegration:
    """Integration tests for typical ClassContext usage patterns."""

    def test_controller_classification_scenario(self):
        """Test typical controller ClassContext setup."""
        ctx = ClassContext(
            fqcn="Drupal\\mymodule\\Controller\\ArticleController",
            short_name="ArticleController",
            file_path=Path("/var/www/drupal/web/modules/custom/mymodule/src/Controller/ArticleController.php"),
            class_line=12,
            parent_classes=["Drupal\\Core\\Controller\\ControllerBase"],
            interfaces=["Drupal\\Core\\DependencyInjection\\ContainerInjectionInterface"],
            traits=["Drupal\\Core\\StringTranslation\\StringTranslationTrait"],
            drupal_type=DrupalClassType.CONTROLLER,
            has_container_injection=True,
            methods=["__construct", "create", "listArticles", "viewArticle"],
            properties=["entityTypeManager", "currentUser"],
        )
        
        # Verify controller patterns
        assert ctx.has_parent("Drupal\\Core\\Controller\\ControllerBase")
        assert ctx.implements_interface("Drupal\\Core\\DependencyInjection\\ContainerInjectionInterface")
        assert ctx.has_container_injection
        assert ctx.drupal_type == DrupalClassType.CONTROLLER
        assert ctx.has_method("create")
        assert ctx.has_method("__construct")

    def test_plugin_classification_scenario(self):
        """Test typical plugin ClassContext setup."""
        ctx = ClassContext(
            fqcn="Drupal\\mymodule\\Plugin\\Block\\FeaturedContentBlock",
            short_name="FeaturedContentBlock",
            file_path=Path("/var/www/drupal/web/modules/custom/mymodule/src/Plugin/Block/FeaturedContentBlock.php"),
            class_line=20,
            parent_classes=[
                "Drupal\\Core\\Block\\BlockBase",
                "Drupal\\Core\\Plugin\\PluginBase",
            ],
            interfaces=[
                "Drupal\\Core\\Block\\BlockPluginInterface",
                "Drupal\\Core\\Plugin\\ContainerFactoryPluginInterface",
            ],
            drupal_type=DrupalClassType.BLOCK,
            has_container_injection=True,
            methods=["build", "blockForm", "blockSubmit", "create"],
        )
        
        # Verify block plugin patterns
        assert ctx.has_parent("Drupal\\Core\\Block\\BlockBase")
        assert ctx.implements_interface("Drupal\\Core\\Plugin\\ContainerFactoryPluginInterface")
        assert ctx.drupal_type == DrupalClassType.BLOCK
        assert ctx.has_method("build")

    def test_event_subscriber_scenario(self):
        """Test typical event subscriber ClassContext setup."""
        ctx = ClassContext(
            fqcn="Drupal\\mymodule\\EventSubscriber\\RequestSubscriber",
            short_name="RequestSubscriber",
            file_path=Path("/var/www/drupal/web/modules/custom/mymodule/src/EventSubscriber/RequestSubscriber.php"),
            class_line=8,
            parent_classes=[],
            interfaces=["Symfony\\Component\\EventDispatcher\\EventSubscriberInterface"],
            drupal_type=DrupalClassType.EVENT_SUBSCRIBER,
            has_container_injection=False,
            methods=["getSubscribedEvents", "onRequest"],
        )
        
        # Verify event subscriber patterns
        assert ctx.implements_interface("Symfony\\Component\\EventDispatcher\\EventSubscriberInterface")
        assert ctx.drupal_type == DrupalClassType.EVENT_SUBSCRIBER
        assert ctx.has_method("getSubscribedEvents")
        assert not ctx.has_container_injection
