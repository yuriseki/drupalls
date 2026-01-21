"""
Tests for DIStrategyFactory.

File: tests/lsp/capabilities/di_refactoring/test_strategy_factory.py
"""
from __future__ import annotations

import pytest

from drupalls.context.types import DrupalClassType
from drupalls.lsp.capabilities.di_refactoring.strategy_factory import (
    DIStrategyFactory,
)
from drupalls.lsp.capabilities.di_refactoring.strategies.controller_strategy import (
    ControllerDIStrategy,
)
from drupalls.lsp.capabilities.di_refactoring.strategies.plugin_strategy import (
    PluginDIStrategy,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def factory() -> DIStrategyFactory:
    """Create a fresh DIStrategyFactory for each test."""
    return DIStrategyFactory()


# ============================================================================
# Tests for get_strategy
# ============================================================================

class TestGetStrategy:
    """Tests for get_strategy method."""

    def test_get_strategy_controller(self, factory: DIStrategyFactory) -> None:
        """Test getting strategy for controller."""
        strategy = factory.get_strategy(DrupalClassType.CONTROLLER)
        
        assert strategy is not None
        assert isinstance(strategy, ControllerDIStrategy)

    def test_get_strategy_form(self, factory: DIStrategyFactory) -> None:
        """Test getting strategy for form."""
        strategy = factory.get_strategy(DrupalClassType.FORM)
        
        assert strategy is not None
        assert isinstance(strategy, ControllerDIStrategy)

    def test_get_strategy_plugin(self, factory: DIStrategyFactory) -> None:
        """Test getting strategy for plugin."""
        strategy = factory.get_strategy(DrupalClassType.PLUGIN)
        
        assert strategy is not None
        assert isinstance(strategy, PluginDIStrategy)

    def test_get_strategy_block(self, factory: DIStrategyFactory) -> None:
        """Test getting strategy for block."""
        strategy = factory.get_strategy(DrupalClassType.BLOCK)
        
        assert strategy is not None
        assert isinstance(strategy, PluginDIStrategy)

    def test_get_strategy_field_formatter(self, factory: DIStrategyFactory) -> None:
        """Test getting strategy for field formatter."""
        strategy = factory.get_strategy(DrupalClassType.FIELD_FORMATTER)
        
        assert strategy is not None
        assert isinstance(strategy, PluginDIStrategy)

    def test_get_strategy_field_widget(self, factory: DIStrategyFactory) -> None:
        """Test getting strategy for field widget."""
        strategy = factory.get_strategy(DrupalClassType.FIELD_WIDGET)
        
        assert strategy is not None
        assert isinstance(strategy, PluginDIStrategy)

    def test_get_strategy_queue_worker(self, factory: DIStrategyFactory) -> None:
        """Test getting strategy for queue worker."""
        strategy = factory.get_strategy(DrupalClassType.QUEUE_WORKER)
        
        assert strategy is not None
        assert isinstance(strategy, PluginDIStrategy)

    def test_get_strategy_unknown_returns_none(
        self, factory: DIStrategyFactory
    ) -> None:
        """Test that unknown type returns None."""
        strategy = factory.get_strategy(DrupalClassType.UNKNOWN)
        
        assert strategy is None

    def test_get_strategy_entity_returns_none(
        self, factory: DIStrategyFactory
    ) -> None:
        """Test that entity type returns None (no strategy)."""
        strategy = factory.get_strategy(DrupalClassType.ENTITY)
        
        assert strategy is None

    def test_get_strategy_service_returns_none(
        self, factory: DIStrategyFactory
    ) -> None:
        """Test that service type returns None (different pattern)."""
        strategy = factory.get_strategy(DrupalClassType.SERVICE)
        
        assert strategy is None


# ============================================================================
# Tests for supports
# ============================================================================

class TestSupports:
    """Tests for supports method."""

    def test_supports_controller(self, factory: DIStrategyFactory) -> None:
        """Test that controller is supported."""
        assert factory.supports(DrupalClassType.CONTROLLER) is True

    def test_supports_form(self, factory: DIStrategyFactory) -> None:
        """Test that form is supported."""
        assert factory.supports(DrupalClassType.FORM) is True

    def test_supports_plugin(self, factory: DIStrategyFactory) -> None:
        """Test that plugin is supported."""
        assert factory.supports(DrupalClassType.PLUGIN) is True

    def test_supports_block(self, factory: DIStrategyFactory) -> None:
        """Test that block is supported."""
        assert factory.supports(DrupalClassType.BLOCK) is True

    def test_supports_field_formatter(self, factory: DIStrategyFactory) -> None:
        """Test that field formatter is supported."""
        assert factory.supports(DrupalClassType.FIELD_FORMATTER) is True

    def test_supports_field_widget(self, factory: DIStrategyFactory) -> None:
        """Test that field widget is supported."""
        assert factory.supports(DrupalClassType.FIELD_WIDGET) is True

    def test_supports_queue_worker(self, factory: DIStrategyFactory) -> None:
        """Test that queue worker is supported."""
        assert factory.supports(DrupalClassType.QUEUE_WORKER) is True

    def test_not_supports_unknown(self, factory: DIStrategyFactory) -> None:
        """Test that unknown is not supported."""
        assert factory.supports(DrupalClassType.UNKNOWN) is False

    def test_not_supports_entity(self, factory: DIStrategyFactory) -> None:
        """Test that entity is not supported."""
        assert factory.supports(DrupalClassType.ENTITY) is False

    def test_not_supports_service(self, factory: DIStrategyFactory) -> None:
        """Test that service type is not supported."""
        assert factory.supports(DrupalClassType.SERVICE) is False

    def test_not_supports_event_subscriber(
        self, factory: DIStrategyFactory
    ) -> None:
        """Test that event subscriber is not supported."""
        assert factory.supports(DrupalClassType.EVENT_SUBSCRIBER) is False
