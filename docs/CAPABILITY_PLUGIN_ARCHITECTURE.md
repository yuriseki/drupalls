# Plugin Architecture for LSP Capabilities

## Overview

This guide shows how to create a plugin architecture for LSP capabilities using the same pattern as the workspace cache system. This allows adding new capability handlers (completion, hover, definition, etc.) without modifying core code.

## Cache Architecture Pattern Analysis

### Key Components of the Cache Plugin System

1. **Base Class (`CachedWorkspace`)**: Abstract base class defining the interface
2. **Data Model (`CachedDataBase`)**: Base dataclass for cached items
3. **Manager (`WorkspaceCache`)**: Central manager that holds all cache plugins
4. **Concrete Implementation (`ServicesCache`)**: Specific cache implementation
5. **Registration**: Dynamic registration via dict in constructor

### Architecture Diagram

```
WorkspaceCache
├── caches: dict[str, CachedWorkspace]
│   ├── "services" -> ServicesCache
│   ├── "hooks" -> HooksCache (future)
│   └── "config" -> ConfigCache (future)
└── Methods: initialize(), invalidate_file()

CachedWorkspace (ABC)
├── initialize()
├── get()
├── get_all()
├── search()
└── ... abstract methods

ServicesCache(CachedWorkspace)
└── Implements all abstract methods
```

## Applying Pattern to LSP Capabilities

### Capability Architecture

LSP capabilities are features like completion, hover, definition, etc. Each capability should be a plugin that can be independently added or removed.

### Architecture Diagram

```
CapabilityManager
├── capabilities: dict[str, Capability]
│   ├── "completion" -> CompletionCapability
│   ├── "hover" -> HoverCapability
│   ├── "definition" -> DefinitionCapability
│   └── "services_completion" -> ServicesCompletionCapability
└── Methods: register_all(), get_capability()

Capability (ABC)
├── register()
├── can_handle()
└── ... abstract methods

ServicesCompletionCapability(Capability)
└── Implements completion for services
```

## Implementation: capabilities.py

```python
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
from typing import TYPE_CHECKING, Any

from lsprotocol.types import (
    CompletionParams,
    CompletionList,
    HoverParams,
    Hover,
    DefinitionParams,
    Location,
)

if TYPE_CHECKING:
    from drupalls.lsp.server import DrupalLanguageServer


class Capability(ABC):
    """
    Base class for all LSP capability handlers.
    
    Each capability can handle one or more LSP features (completion, hover, etc.)
    and decides whether it can handle a specific request based on context.
    """
    
    def __init__(self, server: DrupalLanguageServer) -> None:
        self.server = server
        self.workspace_cache = server.workspace_cache
    
    @abstractmethod
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
    async def definition(self, params: DefinitionParams) -> Location | list[Location] | None:
        """Provide definition location(s)."""
        pass


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
        capabilities: dict[str, Capability] | None = None
    ):
        self.server = server
        
        # Default capabilities
        if capabilities is None:
            from drupalls.lsp.capabilities.services_capabilities import (
                ServicesCompletionCapability,
                ServicesHoverCapability,
            )
            
            capabilities = {
                "services_completion": ServicesCompletionCapability(server),
                "services_hover": ServicesHoverCapability(server),
                # Future capabilities:
                # "hooks_completion": HooksCompletionCapability(server),
                # "config_completion": ConfigCompletionCapability(server),
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
        """Get a specific capability by name."""
        return self.capabilities.get(name)
    
    def get_capabilities_by_type(self, capability_type: type) -> list[Capability]:
        """Get all capabilities of a specific type (e.g., all CompletionCapability)."""
        return [
            cap for cap in self.capabilities.values()
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
                result = await capability.complete(params)
                all_items.extend(result.items)
        
        return CompletionList(is_incomplete=False, items=all_items)
    
    async def handle_hover(self, params: HoverParams) -> Hover | None:
        """
        Handle hover requests by delegating to capable handlers.
        
        Returns the first non-None hover result.
        """
        for capability in self.get_capabilities_by_type(HoverCapability):
            if await capability.can_handle(params):
                result = await capability.hover(params)
                if result:
                    return result
        
        return None
    
    async def handle_definition(self, params: DefinitionParams) -> Location | list[Location] | None:
        """Handle definition requests by delegating to capable handlers."""
        for capability in self.get_capabilities_by_type(DefinitionCapability):
            if await capability.can_handle(params):
                result = await capability.definition(params)
                if result:
                    return result
        
        return None
```

## Implementation: services_capabilities.py

```python
"""
Services-related LSP capabilities.

Provides completion, hover, and definition for Drupal services.
"""

from lsprotocol.types import (
    CompletionParams,
    CompletionList,
    CompletionItem,
    CompletionItemKind,
    HoverParams,
    Hover,
    MarkupContent,
    MarkupKind,
    DefinitionParams,
    Location,
    Range,
    Position,
)

from drupalls.lsp.capabilities.capabilities import (
    CompletionCapability,
    HoverCapability,
    DefinitionCapability,
)


class ServicesCompletionCapability(CompletionCapability):
    """Provides completion for Drupal service names."""
    
    @property
    def name(self) -> str:
        return "services_completion"
    
    @property
    def description(self) -> str:
        return "Autocomplete Drupal service names in ::service() and ->get() calls"
    
    def register(self) -> None:
        """Register is handled by CapabilityManager aggregation."""
        # The CapabilityManager handles registration via handle_completion()
        # Individual capabilities don't register directly with @server.feature()
        pass
    
    async def can_handle(self, params: CompletionParams) -> bool:
        """Check if cursor is in a service context."""
        if not self.workspace_cache:
            return False
        
        # Get document and line
        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line = doc.lines[params.position.line]
        
        # Check for service patterns
        service_patterns = [
            "::service(",
            "->get(",
            "\\Drupal::service(",
        ]
        
        return any(pattern in line for pattern in service_patterns)
    
    async def complete(self, params: CompletionParams) -> CompletionList:
        """Provide service name completions."""
        if not self.workspace_cache:
            return CompletionList(is_incomplete=False, items=[])
        
        # Get services cache
        services_cache = self.workspace_cache.caches.get("services")
        if not services_cache:
            return CompletionList(is_incomplete=False, items=[])
        
        # Get all services
        all_services = services_cache.get_all()
        
        # Build completion items
        items = []
        for service_id, service_def in all_services.items():
            # Get relative path for display
            file_path_str = "unknown"
            if service_def.file_path:
                try:
                    relative = service_def.file_path.relative_to(
                        self.workspace_cache.workspace_root
                    )
                    file_path_str = str(relative)
                except ValueError:
                    file_path_str = str(service_def.file_path)
            
            items.append(
                CompletionItem(
                    label=service_id,
                    kind=CompletionItemKind.Class,
                    detail=service_def.class_name,
                    documentation=f"**Service:** {service_id}\\n\\n"
                                 f"**Class:** {service_def.class_name}\\n\\n"
                                 f"**File:** {file_path_str}",
                    insert_text=service_id,
                )
            )
        
        return CompletionList(is_incomplete=False, items=items)


class ServicesHoverCapability(HoverCapability):
    """Provides hover information for Drupal services."""
    
    @property
    def name(self) -> str:
        return "services_hover"
    
    @property
    def description(self) -> str:
        return "Show information about Drupal services on hover"
    
    def register(self) -> None:
        """Register is handled by CapabilityManager aggregation."""
        pass
    
    async def can_handle(self, params: HoverParams) -> bool:
        """Check if hovering over a service identifier."""
        if not self.workspace_cache:
            return False
        
        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line = doc.lines[params.position.line]
        
        # Simple check: is there a service pattern nearby?
        return "::service(" in line or "->get(" in line
    
    async def hover(self, params: HoverParams) -> Hover | None:
        """Provide hover information for services."""
        if not self.workspace_cache:
            return None
        
        # Get word under cursor (simplified - use LSP word range in production)
        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line = doc.lines[params.position.line]
        
        # Extract service ID (simplified)
        # In production, use proper token extraction
        services_cache = self.workspace_cache.caches.get("services")
        if not services_cache:
            return None
        
        # For demo: try to find any service mentioned in the line
        all_services = services_cache.get_all()
        for service_id, service_def in all_services.items():
            if service_id in line:
                # Found a service!
                relative_path = "unknown"
                if service_def.file_path:
                    try:
                        relative_path = str(
                            service_def.file_path.relative_to(
                                self.workspace_cache.workspace_root
                            )
                        )
                    except ValueError:
                        relative_path = str(service_def.file_path)
                
                content = (
                    f"**Drupal Service:** `{service_id}`\\n\\n"
                    f"**Class:** {service_def.class_name}\\n\\n"
                    f"**Defined in:** {relative_path}\\n\\n"
                )
                
                if service_def.arguments:
                    content += f"**Arguments:** {len(service_def.arguments)}\\n\\n"
                
                if service_def.tags:
                    content += f"**Tags:** {len(service_def.tags)}\\n\\n"
                
                return Hover(
                    contents=MarkupContent(
                        kind=MarkupKind.Markdown,
                        value=content
                    )
                )
        
        return None


class ServicesDefinitionCapability(DefinitionCapability):
    """Provides go-to-definition for Drupal services."""
    
    @property
    def name(self) -> str:
        return "services_definition"
    
    @property
    def description(self) -> str:
        return "Navigate to service definition in .services.yml files"
    
    def register(self) -> None:
        """Register is handled by CapabilityManager aggregation."""
        pass
    
    async def can_handle(self, params: DefinitionParams) -> bool:
        """Check if cursor is on a service identifier."""
        if not self.workspace_cache:
            return False
        
        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line = doc.lines[params.position.line]
        
        return "::service(" in line or "->get(" in line
    
    async def definition(self, params: DefinitionParams) -> Location | None:
        """Provide definition location for services."""
        if not self.workspace_cache:
            return None
        
        # Get service ID under cursor (simplified)
        doc = self.server.workspace.get_text_document(params.text_document.uri)
        line = doc.lines[params.position.line]
        
        services_cache = self.workspace_cache.caches.get("services")
        if not services_cache:
            return None
        
        # Find service in line (simplified)
        all_services = services_cache.get_all()
        for service_id, service_def in all_services.items():
            if service_id in line and service_def.file_path:
                # Return location of the service definition
                # Note: You'd need to parse the YAML to get exact line number
                # For now, return start of file
                return Location(
                    uri=service_def.file_path.as_uri(),
                    range=Range(
                        start=Position(line=0, character=0),
                        end=Position(line=0, character=0),
                    )
                )
        
        return None
```

## Server Integration

Update your `server.py` to use the CapabilityManager:

```python
from drupalls.lsp.capabilities.capabilities import CapabilityManager

def create_server() -> DrupalLanguageServer:
    server = DrupalLanguageServer("drupalls", "0.1.0")
    server.workspace_cache = None
    server.capability_manager = None
    
    @server.feature("initialize")
    async def initialize(ls: DrupalLanguageServer, params):
        # ... workspace_cache initialization ...
        
        # Initialize capability manager
        ls.capability_manager = CapabilityManager(ls)
        ls.capability_manager.register_all()
    
    # Register aggregated handlers
    from lsprotocol.types import TEXT_DOCUMENT_COMPLETION
    
    @server.feature(TEXT_DOCUMENT_COMPLETION)
    async def completion(ls: DrupalLanguageServer, params: CompletionParams):
        if ls.capability_manager:
            return await ls.capability_manager.handle_completion(params)
        return CompletionList(is_incomplete=False, items=[])
    
    return server
```

## Key Parallels with Cache Architecture

| Cache Pattern | Capability Pattern |
|---------------|-------------------|
| `CachedWorkspace` (ABC) | `Capability` (ABC) |
| `ServiceDefinition` (data) | `CompletionItem` (data) |
| `WorkspaceCache` (manager) | `CapabilityManager` (manager) |
| `ServicesCache` (implementation) | `ServicesCompletionCapability` (implementation) |
| `caches: dict[str, CachedWorkspace]` | `capabilities: dict[str, Capability]` |
| `initialize()` | `register()` |
| `get_all()` | `complete()` / `hover()` |

## Benefits of This Architecture

1. **Extensibility**: Add new capabilities without modifying core
2. **Separation of Concerns**: Each capability is self-contained
3. **Testability**: Test capabilities in isolation
4. **Composition**: Multiple capabilities can handle the same feature type
5. **Type Safety**: Abstract base classes enforce interface
6. **Consistency**: Same pattern as workspace cache

## Adding a New Capability

To add hook completion:

```python
# drupalls/lsp/capabilities/hooks_capabilities.py
class HooksCompletionCapability(CompletionCapability):
    @property
    def name(self) -> str:
        return "hooks_completion"
    
    async def can_handle(self, params: CompletionParams) -> bool:
        # Check if in hook context
        pass
    
    async def complete(self, params: CompletionParams) -> CompletionList:
        # Return hook completions
        pass

# In CapabilityManager.__init__():
capabilities = {
    "services_completion": ServicesCompletionCapability(server),
    "hooks_completion": HooksCompletionCapability(server),  # Add this
}
```

No core code modifications needed!
