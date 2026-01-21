# Dependency Injection Code Action

## Overview

This implementation guide documents a **code action** that automatically refactors static Drupal service calls (`\Drupal::service()`, `\Drupal::getContainer()->get()`) into proper **Dependency Injection (DI)** patterns.

The code action is context-aware, using **Phpactor integration** to detect the class type (Controller, Form, Plugin, Service) and applying the appropriate DI strategy for each.

### Key Features

- **Automatic class type detection** via Phpactor
- **Strategy pattern** for different class types
- **Multi-location edits** (property, constructor, create(), usage site)
- **Service lookup** from workspace cache
- **Interface resolution** for common Drupal services

## Problem/Use Case

### The Problem

Drupal developers often write code using static service calls:

```php
// Static calls - hard to test, tightly coupled
$entityTypeManager = \Drupal::entityTypeManager();
$nodes = \Drupal::service('entity_type.manager')->getStorage('node')->loadMultiple();
$messenger = \Drupal::getContainer()->get('messenger');
```

These static calls:
- Make unit testing difficult (can't mock dependencies)
- Create tight coupling to the container
- Violate dependency inversion principle
- Are flagged by Drupal coding standards

### The Solution

A code action that automatically converts static calls to proper DI:

```php
// After refactoring - testable, loosely coupled
class MyController extends ControllerBase {
  protected EntityTypeManagerInterface $entityTypeManager;
  protected MessengerInterface $messenger;
  
  public function __construct(
    EntityTypeManagerInterface $entity_type_manager,
    MessengerInterface $messenger
  ) {
    $this->entityTypeManager = $entity_type_manager;
    $this->messenger = $messenger;
  }
  
  public static function create(ContainerInterface $container): static {
    return new static(
      $container->get('entity_type.manager'),
      $container->get('messenger')
    );
  }
  
  public function myMethod(): array {
    // Now uses injected services
    $nodes = $this->entityTypeManager->getStorage('node')->loadMultiple();
    $this->messenger->addStatus('Done');
    return [];
  }
}
```

## Architecture

### Component Overview

```
DICodeActionCapability
├── Uses: TypeChecker (Phpactor integration)
│   └── ClassContextDetector → ClassContext
│       └── DrupalContextClassifier → DrupalClassType
├── Uses: StaticCallDetector
│   └── Finds \Drupal::service() calls
│   └── Maps shortcuts to service IDs
├── Uses: DIStrategyFactory
│   ├── ControllerDIStrategy (ContainerInjectionInterface)
│   ├── FormDIStrategy (ContainerInjectionInterface)
│   ├── PluginDIStrategy (ContainerFactoryPluginInterface)
│   └── ServiceDIStrategy (services.yml modification)
└── Returns: WorkspaceEdit with all changes
```

### Class Type Detection Flow

```
1. User triggers code action at cursor position
2. TypeChecker.get_class_context() called
   └── Uses Phpactor to get class hierarchy
3. DrupalContextClassifier.classify() determines type
   └── Checks parent classes (ControllerBase, FormBase, BlockBase, etc.)
   └── Checks interfaces (ContainerFactoryPluginInterface, etc.)
4. DIStrategyFactory selects appropriate strategy
5. Strategy generates WorkspaceEdit
```

### DI Strategy Selection

| DrupalClassType | Strategy | Interface Required | create() Signature |
|-----------------|----------|-------------------|-------------------|
| CONTROLLER | ControllerDIStrategy | ContainerInjectionInterface (via ControllerBase) | `create(ContainerInterface $container)` |
| FORM | FormDIStrategy | ContainerInjectionInterface (via FormBase) | `create(ContainerInterface $container)` |
| BLOCK | PluginDIStrategy | ContainerFactoryPluginInterface | `create($container, $configuration, $plugin_id, $plugin_definition)` |
| FIELD_FORMATTER | PluginDIStrategy | ContainerFactoryPluginInterface | `create($container, $configuration, $plugin_id, $plugin_definition)` |
| FIELD_WIDGET | PluginDIStrategy | ContainerFactoryPluginInterface | `create($container, $configuration, $plugin_id, $plugin_definition)` |
| QUEUE_WORKER | PluginDIStrategy | ContainerFactoryPluginInterface | `create($container, $configuration, $plugin_id, $plugin_definition)` |
| SERVICE | ServiceDIStrategy | None | N/A (uses services.yml) |

## Implementation Guide

### Step 1: Add CodeActionCapability Base Class

First, extend the capability system to support code actions.

```python
"""
Code action capability base class.

Add to: drupalls/lsp/capabilities/capabilities.py
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from lsprotocol.types import (
    CodeAction,
    CodeActionParams,
)


class CodeActionCapability(ABC):
    """Base class for code action capabilities."""

    def __init__(self, server) -> None:
        self.server = server
        self.workspace_cache = server.workspace_cache

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this capability."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        pass

    @abstractmethod
    async def can_handle(self, params: CodeActionParams) -> bool:
        """Check if this capability can handle the request."""
        pass

    @abstractmethod
    async def get_code_actions(
        self, params: CodeActionParams
    ) -> list[CodeAction]:
        """Return available code actions for the given context."""
        pass
```

### Step 2: Update CapabilityManager

Add code action handling to the manager.

```python
"""
CapabilityManager updates for code actions.

Add to: drupalls/lsp/capabilities/capabilities.py
"""
from __future__ import annotations

from lsprotocol.types import (
    CodeAction,
    CodeActionParams,
)


class CapabilityManager:
    """Central manager for all LSP capabilities."""

    def __init__(self, server, capabilities: dict | None = None):
        self.server = server
        self.capabilities = capabilities or {}

    async def handle_code_action(
        self, params: CodeActionParams
    ) -> list[CodeAction]:
        """Aggregate code actions from all capable handlers."""
        all_actions: list[CodeAction] = []

        for capability in self.capabilities.values():
            if not isinstance(capability, CodeActionCapability):
                continue

            try:
                if await capability.can_handle(params):
                    actions = await capability.get_code_actions(params)
                    all_actions.extend(actions)
            except Exception as e:
                self.server.show_message_log(
                    f"Code action error in {capability.name}: {e}"
                )

        return all_actions
```

### Step 3: Register Code Action Feature

Register the LSP feature handler in the server.

```python
"""
Server registration for code actions.

Add to: drupalls/lsp/server.py
"""
from __future__ import annotations

from lsprotocol.types import (
    TEXT_DOCUMENT_CODE_ACTION,
    CODE_ACTION_RESOLVE,
    CodeAction,
    CodeActionKind,
    CodeActionParams,
    CodeActionOptions,
)


def register_code_action_handlers(server) -> None:
    """Register code action handlers with the server."""

    @server.feature(
        TEXT_DOCUMENT_CODE_ACTION,
        CodeActionOptions(
            code_action_kinds=[
                CodeActionKind.RefactorRewrite,
                CodeActionKind.QuickFix,
            ],
            resolve_provider=True,
        ),
    )
    async def code_action(
        ls, params: CodeActionParams
    ) -> list[CodeAction] | None:
        """Handle textDocument/codeAction request."""
        if ls.capability_manager:
            actions = await ls.capability_manager.handle_code_action(params)
            return actions if actions else None
        return None

    @server.feature(CODE_ACTION_RESOLVE)
    async def code_action_resolve(ls, action: CodeAction) -> CodeAction:
        """Resolve a code action with full edit details."""
        if ls.capability_manager:
            return await ls.capability_manager.resolve_code_action(action)
        return action
```

### Step 4: Create Static Call Detector

Detect and parse static Drupal service calls.

```python
"""
Static call detector for Drupal service patterns.

File: drupalls/lsp/capabilities/di_refactoring/static_call_detector.py
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class StaticServiceCall:
    """Represents a detected static service call."""

    service_id: str
    line_number: int
    column_start: int
    column_end: int
    full_match: str
    call_type: str  # 'service', 'shortcut', 'container'


# Mapping of Drupal shortcuts to service IDs
DRUPAL_SHORTCUTS: dict[str, str] = {
    "entityTypeManager": "entity_type.manager",
    "database": "database",
    "config": "config.factory",
    "configFactory": "config.factory",
    "currentUser": "current_user",
    "messenger": "messenger",
    "logger": "logger.factory",
    "state": "state",
    "cache": "cache_factory",
    "token": "token",
    "languageManager": "language_manager",
    "moduleHandler": "module_handler",
    "time": "datetime.time",
    "request": "request_stack",
    "routeMatch": "current_route_match",
    "urlGenerator": "url_generator",
    "destination": "redirect.destination",
    "pathValidator": "path.validator",
    "httpClient": "http_client",
    "lock": "lock",
    "queue": "queue",
    "flood": "flood",
    "typedDataManager": "typed_data_manager",
    "transliteration": "transliteration",
    "keyValue": "keyvalue",
    "classResolver": "class_resolver",
}


class StaticCallDetector:
    """Detects static Drupal service calls in PHP code."""

    # Pattern for \Drupal::service('service_id')
    SERVICE_PATTERN = re.compile(
        r"\\Drupal::service\(\s*['\"]([^'\"]+)['\"]\s*\)"
    )

    # Pattern for \Drupal::getContainer()->get('service_id')
    CONTAINER_PATTERN = re.compile(
        r"\\Drupal::getContainer\(\)->get\(\s*['\"]([^'\"]+)['\"]\s*\)"
    )

    # Pattern for \Drupal::shortcutMethod()
    SHORTCUT_PATTERN = re.compile(r"\\Drupal::(\w+)\(\)")

    def detect_all(self, content: str) -> list[StaticServiceCall]:
        """Detect all static service calls in the content."""
        calls: list[StaticServiceCall] = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines):
            calls.extend(self._detect_in_line(line, line_num))

        return calls

    def _detect_in_line(
        self, line: str, line_num: int
    ) -> list[StaticServiceCall]:
        """Detect static calls in a single line."""
        calls: list[StaticServiceCall] = []

        # Check for \Drupal::service('...')
        for match in self.SERVICE_PATTERN.finditer(line):
            calls.append(
                StaticServiceCall(
                    service_id=match.group(1),
                    line_number=line_num,
                    column_start=match.start(),
                    column_end=match.end(),
                    full_match=match.group(0),
                    call_type="service",
                )
            )

        # Check for \Drupal::getContainer()->get('...')
        for match in self.CONTAINER_PATTERN.finditer(line):
            calls.append(
                StaticServiceCall(
                    service_id=match.group(1),
                    line_number=line_num,
                    column_start=match.start(),
                    column_end=match.end(),
                    full_match=match.group(0),
                    call_type="container",
                )
            )

        # Check for \Drupal::shortcutMethod()
        for match in self.SHORTCUT_PATTERN.finditer(line):
            method_name = match.group(1)
            if method_name in DRUPAL_SHORTCUTS:
                calls.append(
                    StaticServiceCall(
                        service_id=DRUPAL_SHORTCUTS[method_name],
                        line_number=line_num,
                        column_start=match.start(),
                        column_end=match.end(),
                        full_match=match.group(0),
                        call_type="shortcut",
                    )
                )

        return calls

    def get_unique_services(
        self, calls: list[StaticServiceCall]
    ) -> dict[str, list[StaticServiceCall]]:
        """Group calls by unique service ID."""
        services: dict[str, list[StaticServiceCall]] = {}
        for call in calls:
            if call.service_id not in services:
                services[call.service_id] = []
            services[call.service_id].append(call)
        return services
```

### Step 5: Service Interface Mapping

Map service IDs to their PHP interface types.

```python
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
```

### Step 6: DI Strategy Base Class

Define the strategy interface for DI refactoring.

```python
"""
DI refactoring strategy base class.

File: drupalls/lsp/capabilities/di_refactoring/strategies/base.py
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from lsprotocol.types import TextEdit, Range, Position, WorkspaceEdit

from drupalls.context.class_context import ClassContext


@dataclass
class DIRefactoringContext:
    """Context for DI refactoring."""

    file_uri: str
    file_content: str
    class_context: ClassContext
    services_to_inject: list[str] = field(default_factory=list)


@dataclass
class RefactoringEdit:
    """A single refactoring edit."""

    description: str
    text_edit: TextEdit


class DIStrategy(ABC):
    """Base class for DI refactoring strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name for display."""
        pass

    @property
    @abstractmethod
    def supported_types(self) -> set[str]:
        """DrupalClassType values this strategy handles."""
        pass

    @abstractmethod
    def generate_edits(
        self, context: DIRefactoringContext
    ) -> list[RefactoringEdit]:
        """Generate edits to convert static calls to DI."""
        pass

    def _create_text_edit(
        self,
        line: int,
        character: int,
        end_line: int,
        end_character: int,
        new_text: str,
    ) -> TextEdit:
        """Helper to create a TextEdit."""
        return TextEdit(
            range=Range(
                start=Position(line=line, character=character),
                end=Position(line=end_line, character=end_character),
            ),
            new_text=new_text,
        )

    def _insert_at(self, line: int, character: int, text: str) -> TextEdit:
        """Create an insert edit at position."""
        return self._create_text_edit(line, character, line, character, text)
```

### Step 7: Controller/Form DI Strategy

Strategy for classes using ContainerInjectionInterface.

```python
"""
DI strategy for Controllers and Forms.

File: drupalls/lsp/capabilities/di_refactoring/strategies/controller_strategy.py
"""
from __future__ import annotations

from drupalls.lsp.capabilities.di_refactoring.strategies.base import (
    DIStrategy,
    DIRefactoringContext,
    RefactoringEdit,
)
from drupalls.lsp.capabilities.di_refactoring.service_interfaces import (
    get_service_interface,
    get_property_name,
)


class ControllerDIStrategy(DIStrategy):
    """DI strategy for Controllers and Forms using ContainerInjectionInterface."""

    @property
    def name(self) -> str:
        return "Controller/Form DI Strategy"

    @property
    def supported_types(self) -> set[str]:
        return {"controller", "form"}

    def generate_edits(
        self, context: DIRefactoringContext
    ) -> list[RefactoringEdit]:
        """Generate edits for Controller/Form DI pattern."""
        edits: list[RefactoringEdit] = []

        # Collect service info
        services_info = []
        for service_id in context.services_to_inject:
            info = get_service_interface(service_id)
            if info:
                services_info.append((service_id, info))
            else:
                # Generate basic info for unknown services
                prop_name = get_property_name(service_id)
                services_info.append((service_id, None, prop_name))

        # Generate use statements
        use_statements = self._generate_use_statements(services_info)
        if use_statements:
            edits.append(
                RefactoringEdit(
                    description="Add use statements",
                    text_edit=self._insert_at(
                        line=self._find_use_insert_line(context),
                        character=0,
                        text=use_statements,
                    ),
                )
            )

        # Generate properties
        properties = self._generate_properties(services_info)
        if properties:
            edits.append(
                RefactoringEdit(
                    description="Add properties",
                    text_edit=self._insert_at(
                        line=context.class_context.class_line + 1,
                        character=0,
                        text=properties,
                    ),
                )
            )

        # Generate constructor
        constructor = self._generate_constructor(services_info)
        if constructor:
            edits.append(
                RefactoringEdit(
                    description="Add/modify constructor",
                    text_edit=self._insert_at(
                        line=self._find_constructor_insert_line(context),
                        character=0,
                        text=constructor,
                    ),
                )
            )

        # Generate create() method
        create_method = self._generate_create_method(services_info)
        if create_method:
            edits.append(
                RefactoringEdit(
                    description="Add/modify create() method",
                    text_edit=self._insert_at(
                        line=self._find_create_insert_line(context),
                        character=0,
                        text=create_method,
                    ),
                )
            )

        return edits

    def _find_use_insert_line(self, context: DIRefactoringContext) -> int:
        """Find line to insert use statements."""
        lines = context.file_content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("class "):
                return i
        return 5  # Default after namespace

    def _find_constructor_insert_line(
        self, context: DIRefactoringContext
    ) -> int:
        """Find line to insert constructor."""
        return context.class_context.class_line + 10  # After properties

    def _find_create_insert_line(self, context: DIRefactoringContext) -> int:
        """Find line to insert create method."""
        return context.class_context.class_line + 5  # After properties

    def _generate_use_statements(self, services_info: list) -> str:
        """Generate use statements for services."""
        statements = []
        for item in services_info:
            if len(item) == 2 and item[1]:
                statements.append(item[1].use_statement)
        # Add ContainerInterface
        statements.append(
            "use Symfony\\Component\\DependencyInjection\\ContainerInterface;"
        )
        return "\n".join(statements) + "\n"

    def _generate_properties(self, services_info: list) -> str:
        """Generate property declarations."""
        lines = ["\n"]
        for item in services_info:
            if len(item) == 2 and item[1]:
                info = item[1]
                lines.append(f"  protected {info.interface_short} ${info.property_name};\n")
            elif len(item) == 3:
                prop_name = item[2]
                lines.append(f"  protected ${prop_name};\n")
        lines.append("\n")
        return "".join(lines)

    def _generate_constructor(self, services_info: list) -> str:
        """Generate constructor."""
        params = []
        assignments = []
        for item in services_info:
            if len(item) == 2 and item[1]:
                info = item[1]
                params.append(f"    {info.interface_short} ${info.property_name}")
                assignments.append(
                    f"    $this->{info.property_name} = ${info.property_name};"
                )
            elif len(item) == 3:
                prop_name = item[2]
                params.append(f"    ${prop_name}")
                assignments.append(f"    $this->{prop_name} = ${prop_name};")

        return (
            "  public function __construct(\n"
            + ",\n".join(params)
            + "\n  ) {\n"
            + "\n".join(assignments)
            + "\n  }\n\n"
        )

    def _generate_create_method(self, services_info: list) -> str:
        """Generate create() method for ContainerInjectionInterface."""
        container_gets = []
        for item in services_info:
            if len(item) == 2:
                service_id = item[0]
                container_gets.append(f"      $container->get('{service_id}')")

        return (
            "  public static function create(ContainerInterface $container): static {\n"
            "    return new static(\n"
            + ",\n".join(container_gets)
            + "\n    );\n"
            "  }\n\n"
        )
```

### Step 8: Plugin DI Strategy

Strategy for classes using ContainerFactoryPluginInterface.

```python
"""
DI strategy for Plugins (Blocks, Field Formatters, QueueWorkers, etc.).

File: drupalls/lsp/capabilities/di_refactoring/strategies/plugin_strategy.py
"""
from __future__ import annotations

from drupalls.lsp.capabilities.di_refactoring.strategies.base import (
    DIStrategy,
    DIRefactoringContext,
    RefactoringEdit,
)
from drupalls.lsp.capabilities.di_refactoring.service_interfaces import (
    get_service_interface,
    get_property_name,
)


class PluginDIStrategy(DIStrategy):
    """DI strategy for Plugins using ContainerFactoryPluginInterface."""

    @property
    def name(self) -> str:
        return "Plugin DI Strategy"

    @property
    def supported_types(self) -> set[str]:
        return {"plugin", "block", "formatter", "widget", "queue_worker"}

    def generate_edits(
        self, context: DIRefactoringContext
    ) -> list[RefactoringEdit]:
        """Generate edits for Plugin DI pattern."""
        edits: list[RefactoringEdit] = []

        # Collect service info
        services_info = []
        for service_id in context.services_to_inject:
            info = get_service_interface(service_id)
            if info:
                services_info.append((service_id, info))

        # Generate interface implementation
        interface_edit = self._generate_interface_implementation(context)
        if interface_edit:
            edits.append(interface_edit)

        # Generate use statements
        use_statements = self._generate_use_statements(services_info)
        if use_statements:
            edits.append(
                RefactoringEdit(
                    description="Add use statements",
                    text_edit=self._insert_at(
                        line=self._find_use_insert_line(context),
                        character=0,
                        text=use_statements,
                    ),
                )
            )

        # Generate properties
        properties = self._generate_properties(services_info)
        if properties:
            edits.append(
                RefactoringEdit(
                    description="Add properties",
                    text_edit=self._insert_at(
                        line=context.class_context.class_line + 1,
                        character=0,
                        text=properties,
                    ),
                )
            )

        # Generate constructor (with plugin args first)
        constructor = self._generate_constructor(services_info)
        if constructor:
            edits.append(
                RefactoringEdit(
                    description="Add/modify constructor",
                    text_edit=self._insert_at(
                        line=self._find_constructor_insert_line(context),
                        character=0,
                        text=constructor,
                    ),
                )
            )

        # Generate create() method (plugin signature)
        create_method = self._generate_create_method(services_info)
        if create_method:
            edits.append(
                RefactoringEdit(
                    description="Add/modify create() method",
                    text_edit=self._insert_at(
                        line=self._find_create_insert_line(context),
                        character=0,
                        text=create_method,
                    ),
                )
            )

        return edits

    def _find_use_insert_line(self, context: DIRefactoringContext) -> int:
        """Find line to insert use statements."""
        lines = context.file_content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("class "):
                return i
        return 5

    def _find_constructor_insert_line(
        self, context: DIRefactoringContext
    ) -> int:
        """Find line to insert constructor."""
        return context.class_context.class_line + 10

    def _find_create_insert_line(self, context: DIRefactoringContext) -> int:
        """Find line to insert create method."""
        return context.class_context.class_line + 5

    def _generate_interface_implementation(
        self, context: DIRefactoringContext
    ) -> RefactoringEdit | None:
        """Add ContainerFactoryPluginInterface to class declaration."""
        # Check if already implements
        if "ContainerFactoryPluginInterface" in context.file_content:
            return None

        # Find class declaration and add interface
        lines = context.file_content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("class ") and "{" in line:
                # Add interface implementation
                new_line = line.rstrip(" {") + " implements ContainerFactoryPluginInterface {"
                return RefactoringEdit(
                    description="Add ContainerFactoryPluginInterface",
                    text_edit=self._create_text_edit(
                        line=i,
                        character=0,
                        end_line=i,
                        end_character=len(line),
                        new_text=new_line,
                    ),
                )
        return None

    def _generate_use_statements(self, services_info: list) -> str:
        """Generate use statements for services."""
        statements = []
        for service_id, info in services_info:
            statements.append(info.use_statement)
        # Add plugin interface
        statements.append(
            "use Drupal\\Core\\Plugin\\ContainerFactoryPluginInterface;"
        )
        statements.append(
            "use Symfony\\Component\\DependencyInjection\\ContainerInterface;"
        )
        return "\n".join(statements) + "\n"

    def _generate_properties(self, services_info: list) -> str:
        """Generate property declarations."""
        lines = ["\n"]
        for service_id, info in services_info:
            lines.append(
                f"  protected {info.interface_short} ${info.property_name};\n"
            )
        lines.append("\n")
        return "".join(lines)

    def _generate_constructor(self, services_info: list) -> str:
        """Generate constructor with plugin args first."""
        # Plugin constructor has standard args first
        plugin_params = [
            "    array $configuration",
            "    $plugin_id",
            "    $plugin_definition",
        ]

        service_params = []
        assignments = []
        for service_id, info in services_info:
            service_params.append(f"    {info.interface_short} ${info.property_name}")
            assignments.append(
                f"    $this->{info.property_name} = ${info.property_name};"
            )

        all_params = plugin_params + service_params

        return (
            "  public function __construct(\n"
            + ",\n".join(all_params)
            + "\n  ) {\n"
            "    parent::__construct($configuration, $plugin_id, $plugin_definition);\n"
            + "\n".join(assignments)
            + "\n  }\n\n"
        )

    def _generate_create_method(self, services_info: list) -> str:
        """Generate create() method for ContainerFactoryPluginInterface."""
        container_gets = []
        for service_id, info in services_info:
            container_gets.append(f"      $container->get('{service_id}')")

        return (
            "  public static function create(\n"
            "    ContainerInterface $container,\n"
            "    array $configuration,\n"
            "    $plugin_id,\n"
            "    $plugin_definition\n"
            "  ): static {\n"
            "    return new static(\n"
            "      $configuration,\n"
            "      $plugin_id,\n"
            "      $plugin_definition,\n"
            + ",\n".join(container_gets)
            + "\n    );\n"
            "  }\n\n"
        )
```

### Step 9: Main Code Action Capability

The main code action capability that ties everything together.

```python
"""
DI refactoring code action capability.

File: drupalls/lsp/capabilities/di_code_action.py
"""
from __future__ import annotations

import re
from lsprotocol.types import (
    CodeAction,
    CodeActionKind,
    CodeActionParams,
    WorkspaceEdit,
    TextEdit,
    Range,
    Position,
)

from drupalls.lsp.capabilities.capabilities import CodeActionCapability
from drupalls.lsp.capabilities.di_refactoring.static_call_detector import (
    StaticCallDetector,
    StaticServiceCall,
)
from drupalls.lsp.capabilities.di_refactoring.strategies.base import (
    DIRefactoringContext,
)
from drupalls.lsp.capabilities.di_refactoring.strategies.controller_strategy import (
    ControllerDIStrategy,
)
from drupalls.lsp.capabilities.di_refactoring.strategies.plugin_strategy import (
    PluginDIStrategy,
)
from drupalls.context.types import DrupalClassType


class DIRefactoringCodeActionCapability(CodeActionCapability):
    """Provides code actions to convert static Drupal calls to DI."""

    def __init__(self, server) -> None:
        super().__init__(server)
        self.static_detector = StaticCallDetector()
        self.strategies = {
            "controller": ControllerDIStrategy(),
            "form": ControllerDIStrategy(),  # Same pattern as controller
            "plugin": PluginDIStrategy(),
            "block": PluginDIStrategy(),
            "formatter": PluginDIStrategy(),
            "widget": PluginDIStrategy(),
            "queue_worker": PluginDIStrategy(),
        }

    @property
    def name(self) -> str:
        return "di_refactoring"

    @property
    def description(self) -> str:
        return "Convert static Drupal service calls to Dependency Injection"

    async def can_handle(self, params: CodeActionParams) -> bool:
        """Check if we can handle this code action request."""
        # Only handle PHP files
        uri = params.text_document.uri
        if not uri.endswith((".php", ".module", ".inc")):
            return False

        # Get document content
        doc = self.server.workspace.get_text_document(uri)
        if not doc:
            return False

        # Check if file has static Drupal calls
        static_calls = self.static_detector.detect_all(doc.source)
        if not static_calls:
            return False

        # Check if we can determine class type
        if self.server.type_checker:
            context = await self.server.type_checker.get_class_context(
                uri, params.range.start
            )
            if context and context.drupal_type != DrupalClassType.UNKNOWN:
                return True

        return False

    async def get_code_actions(
        self, params: CodeActionParams
    ) -> list[CodeAction]:
        """Return available DI refactoring actions."""
        actions: list[CodeAction] = []

        doc = self.server.workspace.get_text_document(params.text_document.uri)
        if not doc:
            return actions

        # Detect static calls
        static_calls = self.static_detector.detect_all(doc.source)
        if not static_calls:
            return actions

        # Get class context
        context = None
        if self.server.type_checker:
            context = await self.server.type_checker.get_class_context(
                params.text_document.uri, params.range.start
            )

        if not context:
            return actions

        # Get unique services
        unique_services = self.static_detector.get_unique_services(static_calls)
        service_ids = list(unique_services.keys())

        # Create action for converting all static calls
        actions.append(
            CodeAction(
                title=f"Convert {len(static_calls)} static calls to Dependency Injection",
                kind=CodeActionKind.RefactorRewrite,
                data={
                    "type": "convert_all_to_di",
                    "uri": params.text_document.uri,
                    "service_ids": service_ids,
                    "class_type": context.drupal_type.value,
                },
            )
        )

        # Create action for single service at cursor
        cursor_call = self._find_call_at_cursor(
            static_calls, params.range.start.line
        )
        if cursor_call:
            actions.append(
                CodeAction(
                    title=f"Inject '{cursor_call.service_id}' service",
                    kind=CodeActionKind.RefactorRewrite,
                    data={
                        "type": "inject_single_service",
                        "uri": params.text_document.uri,
                        "service_id": cursor_call.service_id,
                        "class_type": context.drupal_type.value,
                    },
                )
            )

        return actions

    def _find_call_at_cursor(
        self, calls: list[StaticServiceCall], line: int
    ) -> StaticServiceCall | None:
        """Find the static call at the cursor line."""
        for call in calls:
            if call.line_number == line:
                return call
        return None

    async def resolve(self, action: CodeAction) -> CodeAction:
        """Resolve a code action with full edit details."""
        if not action.data:
            return action

        data = action.data
        action_type = data.get("type")

        if action_type == "convert_all_to_di":
            action.edit = await self._resolve_convert_all(data)
        elif action_type == "inject_single_service":
            action.edit = await self._resolve_inject_single(data)

        return action

    async def _resolve_convert_all(self, data: dict) -> WorkspaceEdit:
        """Resolve full DI conversion."""
        uri = data["uri"]
        service_ids = data["service_ids"]
        class_type = data["class_type"]

        doc = self.server.workspace.get_text_document(uri)
        if not doc:
            return WorkspaceEdit()

        # Get class context
        context = None
        if self.server.type_checker:
            context = await self.server.type_checker.get_class_context(
                uri, Position(line=0, character=0)
            )

        if not context:
            return WorkspaceEdit()

        # Select strategy
        strategy = self.strategies.get(class_type)
        if not strategy:
            return WorkspaceEdit()

        # Create refactoring context
        refactor_context = DIRefactoringContext(
            file_uri=uri,
            file_content=doc.source,
            class_context=context,
            services_to_inject=service_ids,
        )

        # Generate edits
        refactoring_edits = strategy.generate_edits(refactor_context)

        # Also replace static calls with property access
        static_calls = self.static_detector.detect_all(doc.source)
        replacement_edits = self._generate_replacement_edits(
            static_calls, service_ids
        )

        # Combine all edits
        all_text_edits = [e.text_edit for e in refactoring_edits]
        all_text_edits.extend(replacement_edits)

        # Sort by position (reverse order for safe application)
        all_text_edits.sort(
            key=lambda e: (e.range.start.line, e.range.start.character),
            reverse=True,
        )

        return WorkspaceEdit(changes={uri: all_text_edits})

    async def _resolve_inject_single(self, data: dict) -> WorkspaceEdit:
        """Resolve single service injection."""
        # Similar to convert_all but with single service
        return await self._resolve_convert_all({
            **data,
            "service_ids": [data["service_id"]],
        })

    def _generate_replacement_edits(
        self,
        calls: list[StaticServiceCall],
        service_ids: list[str],
    ) -> list[TextEdit]:
        """Generate edits to replace static calls with property access."""
        from drupalls.lsp.capabilities.di_refactoring.service_interfaces import (
            get_property_name,
        )

        edits = []
        for call in calls:
            if call.service_id in service_ids:
                prop_name = get_property_name(call.service_id)
                edits.append(
                    TextEdit(
                        range=Range(
                            start=Position(
                                line=call.line_number,
                                character=call.column_start,
                            ),
                            end=Position(
                                line=call.line_number,
                                character=call.column_end,
                            ),
                        ),
                        new_text=f"$this->{prop_name}",
                    )
                )
        return edits
```

### Step 10: Strategy Factory

Factory to select the appropriate DI strategy.

```python
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
```

## Edge Cases

### 1. Class Already Has Constructor

When the class already has a constructor, the strategy must:
- Parse existing constructor parameters
- Merge new service parameters
- Preserve existing assignments
- Add new assignments

```python
def _merge_constructor(
    self, existing_constructor: str, new_services: list
) -> str:
    """Merge new services into existing constructor."""
    # Parse existing parameters
    # Add new parameters after existing ones
    # Parse existing body
    # Add new assignments
    pass
```

### 2. Class Already Has create() Method

When `create()` already exists:
- Parse existing container->get() calls
- Add new service fetches
- Merge into existing return statement

### 3. Multiple Static Calls to Same Service

When the same service is called multiple times:
- Only inject once
- Replace all calls with the same property access
- Track which calls have been processed

### 4. Static Calls in Non-Class Context

When static calls appear outside a class (procedural code):
- Show warning: "Cannot inject dependencies into procedural code"
- Suggest wrapping in a service class

### 5. Services in Parent Class Constructor

When the parent class already injects some services:
- Check parent constructor signature
- Only inject services not already in parent
- Call parent constructor correctly

### 6. Unknown Services

When a service ID is not in the known mappings:
- Generate generic property name from service ID
- Use `mixed` type or no type hint
- Add TODO comment suggesting to add proper type

## Testing

### Unit Tests for Static Call Detector

```python
"""
Tests for StaticCallDetector.

File: tests/lsp/capabilities/di_refactoring/test_static_call_detector.py
"""
from __future__ import annotations

import pytest
from drupalls.lsp.capabilities.di_refactoring.static_call_detector import (
    StaticCallDetector,
    DRUPAL_SHORTCUTS,
)


class TestStaticCallDetector:
    """Tests for StaticCallDetector."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.detector = StaticCallDetector()

    def test_detect_service_call(self) -> None:
        """Test detection of Drupal::service() calls."""
        content = r"$manager = \Drupal::service('entity_type.manager');"
        calls = self.detector.detect_all(content)
        
        assert len(calls) == 1
        assert calls[0].service_id == "entity_type.manager"
        assert calls[0].call_type == "service"

    def test_detect_container_get(self) -> None:
        """Test detection of getContainer()->get() calls."""
        content = r"$messenger = \Drupal::getContainer()->get('messenger');"
        calls = self.detector.detect_all(content)
        
        assert len(calls) == 1
        assert calls[0].service_id == "messenger"
        assert calls[0].call_type == "container"

    def test_detect_shortcut_method(self) -> None:
        """Test detection of Drupal shortcut methods."""
        content = r"$etm = \Drupal::entityTypeManager();"
        calls = self.detector.detect_all(content)
        
        assert len(calls) == 1
        assert calls[0].service_id == "entity_type.manager"
        assert calls[0].call_type == "shortcut"

    def test_detect_multiple_calls(self) -> None:
        """Test detection of multiple static calls."""
        content = """
        $etm = \\Drupal::entityTypeManager();
        $messenger = \\Drupal::service('messenger');
        $db = \\Drupal::database();
        """
        calls = self.detector.detect_all(content)
        
        assert len(calls) == 3

    def test_get_unique_services(self) -> None:
        """Test grouping calls by service ID."""
        content = """
        $etm1 = \\Drupal::entityTypeManager();
        $etm2 = \\Drupal::service('entity_type.manager');
        """
        calls = self.detector.detect_all(content)
        unique = self.detector.get_unique_services(calls)
        
        assert len(unique) == 1
        assert "entity_type.manager" in unique
        assert len(unique["entity_type.manager"]) == 2
```

### Integration Tests for Code Action

```python
"""
Integration tests for DI code action.

File: tests/lsp/capabilities/test_di_code_action.py
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock
from lsprotocol.types import (
    CodeActionParams,
    TextDocumentIdentifier,
    Range,
    Position,
)

from drupalls.lsp.capabilities.di_code_action import (
    DIRefactoringCodeActionCapability,
)
from drupalls.context.class_context import ClassContext
from drupalls.context.types import DrupalClassType


class TestDICodeActionCapability:
    """Tests for DIRefactoringCodeActionCapability."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.server = MagicMock()
        self.server.workspace_cache = MagicMock()
        self.server.type_checker = AsyncMock()
        self.capability = DIRefactoringCodeActionCapability(self.server)

    @pytest.mark.asyncio
    async def test_can_handle_php_file_with_static_calls(self) -> None:
        """Test can_handle returns True for PHP with static calls."""
        # Setup mock document
        mock_doc = MagicMock()
        mock_doc.source = r"\Drupal::service('entity_type.manager');"
        self.server.workspace.get_text_document.return_value = mock_doc

        # Setup mock class context
        context = ClassContext(
            fqcn="Drupal\\mymodule\\Controller\\TestController",
            short_name="TestController",
            file_path="/path/to/TestController.php",
            class_line=10,
            drupal_type=DrupalClassType.CONTROLLER,
        )
        self.server.type_checker.get_class_context.return_value = context

        params = CodeActionParams(
            text_document=TextDocumentIdentifier(uri="file:///test.php"),
            range=Range(
                start=Position(line=0, character=0),
                end=Position(line=0, character=0),
            ),
        )

        result = await self.capability.can_handle(params)
        assert result is True

    @pytest.mark.asyncio
    async def test_can_handle_non_php_file(self) -> None:
        """Test can_handle returns False for non-PHP files."""
        params = CodeActionParams(
            text_document=TextDocumentIdentifier(uri="file:///test.js"),
            range=Range(
                start=Position(line=0, character=0),
                end=Position(line=0, character=0),
            ),
        )

        result = await self.capability.can_handle(params)
        assert result is False
```

## Performance Considerations

### 1. Lazy Resolution

Use lazy code action resolution for expensive edit generation:
- Initial `get_code_actions()` only determines availability
- Full edit generation happens in `resolve()` when user selects action
- Reduces response time for code action menu

### 2. Cache Class Context

Cache Phpactor class context results:
- Class hierarchy rarely changes during editing
- Invalidate on file save
- Reduces Phpactor CLI calls

### 3. Quick Applicability Check

Perform fast checks before expensive analysis:
- Check file extension first (.php only)
- Quick regex scan for `\Drupal::` before full detection
- Skip if no static calls found

```python
def _quick_check(self, content: str) -> bool:
    """Fast check for potential static calls."""
    return r"\Drupal::" in content
```

## Integration

### With Existing Capabilities

The DI code action integrates with:

1. **ServicesCache**: Look up service definitions for validation
2. **TypeChecker**: Get class context from Phpactor
3. **DrupalContextClassifier**: Determine class type
4. **CapabilityManager**: Register as code action capability

### Registration

```python
# In CapabilityManager.__init__
self.capabilities["di_refactoring"] = DIRefactoringCodeActionCapability(server)
```

### Server Configuration

```python
# In server initialization
CodeActionOptions(
    code_action_kinds=[
        CodeActionKind.RefactorRewrite,
    ],
    resolve_provider=True,
)
```

## Future Enhancements

1. **Service YAML Updates**: For custom services, also update `*.services.yml`
2. **Batch Refactoring**: Refactor all files in module at once
3. **Undo Support**: Track changes for easy reversal
4. **Preview**: Show diff before applying changes
5. **Configuration**: User settings for code style preferences
6. **Custom Interface Mappings**: Allow project-specific service-to-interface mappings

## References

### LSP Specification
- [Code Action Request](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocument_codeAction)
- [WorkspaceEdit](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#workspaceEdit)

### Drupal Documentation
- [Services and Dependency Injection](https://www.drupal.org/docs/drupal-apis/services-and-dependency-injection)
- [ContainerInjectionInterface](https://api.drupal.org/api/drupal/core!lib!Drupal!Core!DependencyInjection!ContainerInjectionInterface.php/interface/ContainerInjectionInterface)
- [ContainerFactoryPluginInterface](https://api.drupal.org/api/drupal/core!lib!Drupal!Core!Plugin!ContainerFactoryPluginInterface.php/interface/ContainerFactoryPluginInterface)

### Project Files
- `drupalls/lsp/capabilities/capabilities.py` - Base capability classes
- `drupalls/context/drupal_classifier.py` - Class type classification
- `drupalls/lsp/type_checker.py` - Phpactor integration

## Next Steps

1. **Implement the base code action capability** in capabilities.py
2. **Create the di_refactoring module** with detector and strategies
3. **Add unit tests** for each component
4. **Integration testing** with real PHP files
5. **Register in CapabilityManager** and server
6. **Document in APPENDIX** the service interface mappings
