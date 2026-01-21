"""
LSP Capabilities Manager

This module manages LSP feature handlers (completion, hover, etc.) using
a plugin architecture similar to WorkspaceCache.

Design Principles:
1. Plugin-based (add capabilities without modifying core)
2. Type-safe (abstract base class)
3. Composable (multiple handlers for same feature)
4. Testable (isolated capability handlers)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from lsprotocol.types import (
    CodeAction,
    CodeActionParams,
    CompletionList,
    CompletionParams,
    DefinitionParams,
    Hover,
    HoverParams,
    Location,
    LogMessageParams,
    MessageType,
    ReferenceParams,
)


if TYPE_CHECKING:
    from drupalls.lsp.drupal_language_server import DrupalLanguageServer


class Capability(ABC):
    """
    Base class for all LSP capability handlers.

    Each capability can handle one or more LSP features (completion, hover, etc.)
    and decides whether it can handle a specific request based on context.
    """

    def __init__(self, server: DrupalLanguageServer) -> None:
        self.server = server
        self.workspace_cache = server.workspace_cache

    def register(self) -> None:
        """
        Register LSP feature handlers with the server.

        This is called once during server initialization to set up
        all @server.feature() decorators for this capability.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this capability."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this capability does."""
        pass

    @abstractmethod
    async def can_handle(self, params) -> bool:
        """Check if the capability can handle the request."""
        pass


class CompletionCapability(Capability):
    """Base class for completion capabilities."""

    @abstractmethod
    async def can_handle(self, params: CompletionParams) -> bool:
        """
        Check if this capability can handle the completion request.

        Returns True if this capability should provide completions
        for the current context.
        """
        pass

    @abstractmethod
    async def complete(self, params: CompletionParams) -> CompletionList:
        """
        Provide completion items.

        Only called if can_handle() returns True.
        """
        pass


class HoverCapability(Capability):
    """Base class for hover capabilities."""

    @abstractmethod
    async def can_handle(self, params: HoverParams) -> bool:
        """Check if this capability can handle the hover request."""
        pass

    @abstractmethod
    async def hover(self, params: HoverParams) -> Hover | None:
        """Provide hover information."""
        pass


class DefinitionCapability(Capability):
    """Base class for definition capabilities."""

    @abstractmethod
    async def can_handle(self, params: DefinitionParams) -> bool:
        """Check if this capability can handle the definition request."""
        pass

    @abstractmethod
    async def definition(
        self, params: DefinitionParams
    ) -> Location | list[Location] | None:
        """Provide definition location(s)"""
        pass


class ReferencesCapability(Capability):
    """Base class for references capabilities."""

    @abstractmethod
    async def can_handle(self, params: ReferenceParams) -> bool:
        pass

    @abstractmethod
    async def find_references(self, params: ReferenceParams) -> list[Location]:
        pass


class CodeActionCapability(Capability):
    """Base class for code action capabilities."""

    @abstractmethod
    async def can_handle(self, params: CodeActionParams) -> bool:
        """Check if this capability can handle the code action request."""
        pass

    @abstractmethod
    async def get_code_actions(
        self, params: CodeActionParams
    ) -> list[CodeAction]:
        """Return available code actions for the given context."""
        pass

    async def resolve(self, action: CodeAction) -> CodeAction:
        """
        Resolve a code action with full edit details.
        
        Override this method to provide lazy resolution of edit details.
        By default, returns the action unchanged.
        """
        return action


class CapabilityManager:
    """
    Central manager for all LSP capabilities.

    Similar to WorkspaceCache, this manages all capability plugins
    and provides methods to register and access them.

    Usage:
        # In server initialization
        manager = CapabilityManager(server)
        manager.register_all()

        # Capabilities are automatically registered with server
    """

    def __init__(
        self,
        server: DrupalLanguageServer,
        capabilities: dict[str, Capability] | None = None,
    ):
        self.server = server

        # Default capabilities
        if capabilities is None:
            from drupalls.lsp.capabilities.services_capabilities import (
                ServicesCompletionCapability,
                ServicesDefinitionCapability,
                ServicesHoverCapability,
                ServicesYamlDefinitionCapability,
                ServicesReferencesCapability,
            )
            from drupalls.lsp.capabilities.di_code_action import (
                DIRefactoringCodeActionCapability,
            )

            capabilities = {
                "services_completion": ServicesCompletionCapability(server),
                "services_hover": ServicesHoverCapability(server),
                "services_definition": ServicesDefinitionCapability(server),
                "services_yaml_definition": ServicesYamlDefinitionCapability(server),
                "services_references": ServicesReferencesCapability(server),
                "di_refactoring": DIRefactoringCodeActionCapability(server),
                # TODO: Implements other capabilities.
                # "hooks_completion": HooksCompletionCapability(server)
                # "config_completion": ConfigCompletionCapability(server)
            }

        self.capabilities = capabilities
        self._registered = False

    def register_all(self) -> None:
        """Register all capabilities with the server."""
        if self._registered:
            return

        for capability in self.capabilities.values():
            capability.register()

        self._registered = True

    def get_capability(self, name: str) -> Capability | None:
        """Get a specific capability by name"""
        return self.capabilities.get(name)

    def get_capabilities_by_type(self, capability_type: type) -> list[Capability]:
        """Get all capabilities of a specific type (e.g., all CompletionCapability)."""
        return [
            cap
            for cap in self.capabilities.values()
            if isinstance(cap, capability_type)
        ]

    async def handle_completion(self, params: CompletionParams) -> CompletionList:
        """
        Handle completion requests by delegating to capable handlers.

        This aggregates results from all completion capabilities that
        can handle the request.
        """
        all_items = []

        for capability in self.get_capabilities_by_type(CompletionCapability):
            if await capability.can_handle(params):
                result = await capability.complete(params)  # pyright: ignore
                all_items.extend(result.items)

        return CompletionList(is_incomplete=False, items=all_items)

    async def handle_hover(self, params: HoverParams) -> Hover | None:
        """
        Handle hover requests by delegating to capable handlers.

        Returns the first non-None hover result
        """
        for capability in self.get_capabilities_by_type(HoverCapability):
            if await capability.can_handle(params):
                result = await capability.hover(params)  # pyright: ignore
                if result:
                    return result

        return None

    async def handle_definition(
        self, params: DefinitionParams
    ) -> Location | list[Location] | None:
        """Handle definition requests by delegating to capable handlers."""
        for capability in self.get_capabilities_by_type(DefinitionCapability):
            if await capability.can_handle(params):
                result = await capability.definition(params)  # pyright: ignore
                if result:
                    return result

        return None

    async def handle_references(self, params: ReferenceParams) -> list[Location] | None:
        """Handle references request by delegating to capable handlers."""
        for capability in self.get_capabilities_by_type(ReferencesCapability):
            if await capability.can_handle(params):
                result = await capability.find_references(params)  # pyright: ignore
                if result:
                    return result

        return None

    async def handle_code_action(
        self, params: CodeActionParams
    ) -> list[CodeAction]:
        """Aggregate code actions from all capable handlers."""
        all_actions: list[CodeAction] = []

        for capability in self.get_capabilities_by_type(CodeActionCapability):
            try:
                if await capability.can_handle(params):
                    actions = await capability.get_code_actions(params)  # pyright: ignore
                    all_actions.extend(actions)
            except Exception as e:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Error,
                        message=f"Code action error in {capability.name}: {e}"
                    )
                )

        return all_actions

    async def resolve_code_action(self, action: CodeAction) -> CodeAction:
        """Resolve a code action with full edit details."""
        for capability in self.get_capabilities_by_type(CodeActionCapability):
            try:
                resolved = await capability.resolve(action)  # pyright: ignore
                if resolved.edit:
                    return resolved
            except Exception as e:
                self.server.window_log_message(
                    LogMessageParams(
                        type=MessageType.Error,
                        message=f"Code action resolve error in {capability.name}: {e}"
                    )
                )

        return action
