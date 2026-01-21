"""
DI strategy factory.

File: drupalls/lsp/capabilities/di_refactoring/strategy_factory.py
"""
from __future__ import annotations

from drupalls.context.types import DrupalClassType
from drupalls.lsp.capabilities.di_refactoring.strategies.base import DIStrategy
from drupalls.lsp.capabilities.di_refactoring.strategies.controller_strategy import (
    ControllerDIStrategy,
)
from drupalls.lsp.capabilities.di_refactoring.strategies.plugin_strategy import (
    PluginDIStrategy,
)


class DIStrategyFactory:
    """Factory for selecting DI refactoring strategies."""

    def __init__(self) -> None:
        self._strategies: dict[DrupalClassType, DIStrategy] = {
            DrupalClassType.CONTROLLER: ControllerDIStrategy(),
            DrupalClassType.FORM: ControllerDIStrategy(),
            DrupalClassType.PLUGIN: PluginDIStrategy(),
            DrupalClassType.BLOCK: PluginDIStrategy(),
            DrupalClassType.FIELD_FORMATTER: PluginDIStrategy(),
            DrupalClassType.FIELD_WIDGET: PluginDIStrategy(),
            DrupalClassType.QUEUE_WORKER: PluginDIStrategy(),
        }

    def get_strategy(self, class_type: DrupalClassType) -> DIStrategy | None:
        """Get the appropriate strategy for a class type."""
        return self._strategies.get(class_type)

    def supports(self, class_type: DrupalClassType) -> bool:
        """Check if a class type is supported for DI refactoring."""
        return class_type in self._strategies
