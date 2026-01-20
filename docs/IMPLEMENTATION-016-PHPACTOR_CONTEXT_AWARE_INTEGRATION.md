# Context-Aware Phpactor Integration

## Overview

This guide restructures the Phpactor integration to provide **context-aware PHP class analysis**. The new architecture detects what Drupal construct (Controller, Form, Plugin, Service, etc.) the cursor is currently inside, along with its parent classes and implemented interfaces.

### Problem Statement

The current Phpactor integration has significant limitations:

1. **Single-purpose design**: Only checks if a variable is `ContainerInterface` for service completion
2. **No class context detection**: Cannot determine if the cursor is inside a Controller, Form, Plugin, or custom service
3. **No inheritance analysis**: Cannot detect parent classes or implemented interfaces
4. **Two competing implementations**: 
   - `phpactor_integration.py` (active, async CLI)
   - `phpactor_cli.py` (unused, sync with RPC support)
5. **Hard to maintain**: Tightly coupled methods with complex logic

### Solution

Restructure into a modular architecture with clear separation of concerns:

| Component | Responsibility |
|-----------|---------------|
| `PhpactorClient` | Low-level Phpactor CLI/RPC communication |
| `ClassContext` | Data structure holding class information |
| `ClassContextDetector` | Detects class at cursor, extracts hierarchy |
| `DrupalContextClassifier` | Maps PHP classes to Drupal constructs |
| `TypeChecker` | Refactored to use new components |

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DrupalLanguageServer                             │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                    Capabilities Layer                                ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  ││
│  │  │ Completion  │  │    Hover    │  │ Definition  │                  ││
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                  ││
│  └─────────┼────────────────┼────────────────┼──────────────────────────┘│
│            │                │                │                           │
│            ▼                ▼                ▼                           │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                   Context Detection Layer                            ││
│  │  ┌──────────────────────┐    ┌──────────────────────────────┐       ││
│  │  │ ClassContextDetector │───▶│ DrupalContextClassifier      │       ││
│  │  │                      │    │                              │       ││
│  │  │ get_class_at_pos()   │    │ classify(ClassContext)       │       ││
│  │  │ get_class_hierarchy()│    │ → DrupalClassType            │       ││
│  │  └──────────┬───────────┘    └──────────────────────────────┘       ││
│  └─────────────┼────────────────────────────────────────────────────────┘│
│                │                                                         │
│                ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                     Phpactor Client Layer                            ││
│  │  ┌──────────────────────────────────────────────────────────┐       ││
│  │  │                    PhpactorClient                         │       ││
│  │  │                                                           │       ││
│  │  │  offset_info(file, offset) → TypeInfo                     │       ││
│  │  │  class_reflect(file, offset) → ClassReflection            │       ││
│  │  │  references(file, offset) → list[Reference]               │       ││
│  │  └──────────────────────────────────────────────────────────┘       ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                │                                                         │
└────────────────┼─────────────────────────────────────────────────────────┘
                 │
                 ▼
        ┌────────────────┐
        │  Phpactor CLI  │
        │  (subprocess)  │
        └────────────────┘
```

### Data Flow

```
User types in PHP file
         ↓
LSP Capability receives request (position, uri)
         ↓
ClassContextDetector.get_class_at_position(uri, position)
         ↓
PhpactorClient.class_reflect(file, offset)
         ↓
Parse response → ClassContext dataclass
         ↓
DrupalContextClassifier.classify(context)
         ↓
ClassContext with drupal_type set
         ↓
Capability uses context for intelligent responses
```

## Implementation Guide

### Step 1: Create Data Structures

#### DrupalClassType Enum

```python
# drupalls/context/types.py

from enum import Enum


class DrupalClassType(Enum):
    """Classification of Drupal PHP class types."""
    
    CONTROLLER = "controller"       # extends ControllerBase
    FORM = "form"                   # extends FormBase, ConfigFormBase
    PLUGIN = "plugin"               # has @Plugin annotation or extends PluginBase
    ENTITY = "entity"               # extends ContentEntityBase, ConfigEntityBase
    SERVICE = "service"             # registered in services.yml
    EVENT_SUBSCRIBER = "subscriber" # implements EventSubscriberInterface
    ACCESS_CHECKER = "access"       # implements AccessInterface
    BLOCK = "block"                 # extends BlockBase (also a plugin)
    FIELD_FORMATTER = "formatter"   # extends FormatterBase
    FIELD_WIDGET = "widget"         # extends WidgetBase
    MIGRATION = "migration"         # extends MigrationBase
    QUEUE_WORKER = "queue_worker"   # extends QueueWorkerBase
    CONSTRAINT = "constraint"       # extends Constraint
    UNKNOWN = "unknown"
```

#### ClassContext Dataclass

```python
# drupalls/context/class_context.py

from dataclasses import dataclass, field
from pathlib import Path

from drupalls.context.types import DrupalClassType


@dataclass
class ClassContext:
    """
    Holds detected PHP class information at a cursor position.
    
    This dataclass contains everything needed to understand the current
    class context for intelligent LSP features.
    """
    
    # Fully qualified class name (e.g., "Drupal\\mymodule\\Controller\\MyController")
    fqcn: str
    
    # Short class name (e.g., "MyController")
    short_name: str
    
    # File path where the class is defined
    file_path: Path
    
    # Line number where class declaration starts (0-indexed)
    class_line: int
    
    # Parent classes in inheritance order (immediate parent first)
    parent_classes: list[str] = field(default_factory=list)
    
    # Implemented interfaces
    interfaces: list[str] = field(default_factory=list)
    
    # Used traits
    traits: list[str] = field(default_factory=list)
    
    # Drupal classification (set by DrupalContextClassifier)
    drupal_type: DrupalClassType = DrupalClassType.UNKNOWN
    
    # Whether the class uses ContainerInjectionInterface pattern
    has_container_injection: bool = False
    
    # Methods defined in this class
    methods: list[str] = field(default_factory=list)
    
    # Properties defined in this class
    properties: list[str] = field(default_factory=list)
    
    def has_parent(self, parent_fqcn: str) -> bool:
        """Check if class extends a specific parent (at any level)."""
        parent_lower = parent_fqcn.lower()
        return any(p.lower() == parent_lower for p in self.parent_classes)
    
    def implements_interface(self, interface_fqcn: str) -> bool:
        """Check if class implements a specific interface."""
        interface_lower = interface_fqcn.lower()
        return any(i.lower() == interface_lower for i in self.interfaces)
    
    def has_method(self, method_name: str) -> bool:
        """Check if class defines a specific method."""
        return method_name in self.methods
```

### Step 2: Refactor PhpactorClient

Unify the two existing implementations into a clean, well-structured client:

```python
# drupalls/phpactor/client.py

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TypeInfo:
    """Type information returned by Phpactor."""
    type_name: str | None
    symbol_type: str | None  # "class", "method", "property", "variable"
    fqcn: str | None
    offset: int
    

@dataclass
class ClassReflection:
    """Class reflection data from Phpactor."""
    fqcn: str
    short_name: str
    parent_class: str | None
    interfaces: list[str]
    traits: list[str]
    methods: list[str]
    properties: list[str]
    is_abstract: bool
    is_final: bool


class PhpactorClient:
    """
    Unified client for Phpactor CLI/RPC communication.
    
    This client wraps all Phpactor interactions, providing both
    synchronous and asynchronous methods for querying PHP code.
    """
    
    def __init__(self, drupalls_root: Path | None = None):
        """
        Initialize Phpactor client.
        
        Args:
            drupalls_root: Root directory of DrupalLS installation.
                          Auto-detects if None.
        """
        if drupalls_root is None:
            current_file = Path(__file__).resolve()
            drupalls_root = current_file.parent.parent.parent
        
        self.drupalls_root = drupalls_root
        self.phpactor_dir = drupalls_root / "phpactor"
        self.phpactor_bin = self.phpactor_dir / "bin" / "phpactor"
        
        # Cache for class reflections
        self._reflection_cache: dict[str, ClassReflection] = {}
    
    def is_available(self) -> bool:
        """Check if Phpactor CLI is available and working."""
        if not self.phpactor_bin.exists():
            return False
        
        try:
            import subprocess
            result = subprocess.run(
                [str(self.phpactor_bin), "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    async def offset_info(
        self,
        file_path: Path,
        offset: int,
        working_dir: Path | None = None
    ) -> TypeInfo | None:
        """
        Get type information at a specific byte offset.
        
        Args:
            file_path: Path to PHP file
            offset: Byte offset in file
            working_dir: Working directory for Phpactor (project root)
        
        Returns:
            TypeInfo with type details, or None if not found
        """
        try:
            cmd = [
                str(self.phpactor_bin),
                "offset:info",
                "--working-dir", str(working_dir or file_path.parent),
                str(file_path),
                str(offset)
            ]
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(working_dir or file_path.parent)
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                return None
            
            parsed = self._parse_cli_output(stdout.decode())
            
            return TypeInfo(
                type_name=parsed.get("type"),
                symbol_type=parsed.get("symbol type"),
                fqcn=parsed.get("class"),
                offset=offset
            )
            
        except Exception:
            return None
    
    async def class_reflect(
        self,
        file_path: Path,
        offset: int,
        working_dir: Path | None = None
    ) -> ClassReflection | None:
        """
        Get full class reflection at offset using RPC.
        
        Args:
            file_path: Path to PHP file
            offset: Byte offset in file (anywhere in class)
            working_dir: Working directory for Phpactor
        
        Returns:
            ClassReflection with full class details, or None
        """
        try:
            response = await self._rpc_command_async(
                "class_reflect",
                {
                    "source": str(file_path),
                    "offset": offset
                },
                working_dir=working_dir or file_path.parent
            )
            
            if not response:
                return None
            
            # Parse the reflection response
            return ClassReflection(
                fqcn=response.get("class", ""),
                short_name=response.get("name", ""),
                parent_class=response.get("parent"),
                interfaces=response.get("interfaces", []),
                traits=response.get("traits", []),
                methods=[m["name"] for m in response.get("methods", [])],
                properties=[p["name"] for p in response.get("properties", [])],
                is_abstract=response.get("abstract", False),
                is_final=response.get("final", False)
            )
            
        except Exception:
            return None
    
    async def get_class_hierarchy(
        self,
        fqcn: str,
        working_dir: Path
    ) -> list[str]:
        """
        Get full class hierarchy (all parent classes).
        
        Args:
            fqcn: Fully qualified class name
            working_dir: Project working directory
        
        Returns:
            List of parent classes in order (immediate parent first)
        """
        hierarchy: list[str] = []
        current_class = fqcn
        seen: set[str] = set()
        
        while current_class and current_class not in seen:
            seen.add(current_class)
            
            response = await self._rpc_command_async(
                "class_reflect",
                {"class": current_class},
                working_dir=working_dir
            )
            
            if not response:
                break
            
            parent = response.get("parent")
            if parent:
                hierarchy.append(parent)
                current_class = parent
            else:
                break
        
        return hierarchy
    
    async def _rpc_command_async(
        self,
        action: str,
        parameters: dict,
        working_dir: Path
    ) -> dict | None:
        """Execute RPC command asynchronously."""
        try:
            rpc_data = {"action": action, "parameters": parameters}
            
            cmd = [
                str(self.phpactor_bin),
                "rpc",
                "--working-dir", str(working_dir)
            ]
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(working_dir)
            )
            
            stdout, stderr = await result.communicate(
                input=json.dumps(rpc_data).encode()
            )
            
            if result.returncode != 0:
                return None
            
            return json.loads(stdout.decode())
            
        except Exception:
            return None
    
    def _parse_cli_output(self, output: str) -> dict[str, str]:
        """Parse phpactor offset:info CLI output into key-value pairs."""
        lines = output.strip().split("\n")
        parsed: dict[str, str] = {}
        
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                parsed[key.strip().lower()] = value.strip()
        
        return parsed
    
    def clear_cache(self) -> None:
        """Clear all internal caches."""
        self._reflection_cache.clear()
```

### Step 3: Implement ClassContextDetector

```python
# drupalls/context/class_context_detector.py

import re
from pathlib import Path

from lsprotocol.types import Position

from drupalls.context.class_context import ClassContext
from drupalls.context.types import DrupalClassType
from drupalls.phpactor.client import PhpactorClient


class ClassContextDetector:
    """
    Detects PHP class context at a given cursor position.
    
    This class is responsible for determining what class the cursor
    is currently inside, and gathering all relevant information about
    that class including parent classes and interfaces.
    """
    
    def __init__(self, phpactor_client: PhpactorClient):
        """
        Initialize detector with Phpactor client.
        
        Args:
            phpactor_client: Configured PhpactorClient instance
        """
        self.phpactor = phpactor_client
        self._context_cache: dict[tuple[str, int], ClassContext] = {}
    
    async def get_class_at_position(
        self,
        uri: str,
        position: Position,
        doc_lines: list[str] | None = None
    ) -> ClassContext | None:
        """
        Get the class context at a specific cursor position.
        
        Args:
            uri: Document URI (file://...)
            position: Cursor position (line, character)
            doc_lines: Optional document lines for offset calculation
        
        Returns:
            ClassContext if cursor is inside a class, None otherwise
        """
        file_path = Path(uri.replace("file://", ""))
        
        if not file_path.exists() or not file_path.suffix == ".php":
            return None
        
        # Check cache
        cache_key = (uri, position.line)
        if cache_key in self._context_cache:
            return self._context_cache[cache_key]
        
        # Read file if lines not provided
        if doc_lines is None:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    doc_lines = f.readlines()
            except Exception:
                return None
        
        # First, find if we're inside a class using regex
        class_info = self._find_enclosing_class(doc_lines, position.line)
        if class_info is None:
            return None
        
        class_name, class_line = class_info
        
        # Calculate offset to class declaration
        offset = self._position_to_offset(doc_lines, Position(line=class_line, character=0))
        
        # Find project root
        working_dir = self._find_project_root(file_path)
        
        # Get class reflection from Phpactor
        reflection = await self.phpactor.class_reflect(
            file_path, offset, working_dir
        )
        
        if reflection is None:
            # Fallback: create basic context from regex parsing
            context = self._create_context_from_regex(
                file_path, doc_lines, class_line, class_name
            )
        else:
            # Get full hierarchy
            hierarchy = await self.phpactor.get_class_hierarchy(
                reflection.fqcn, working_dir
            )
            
            context = ClassContext(
                fqcn=reflection.fqcn,
                short_name=reflection.short_name,
                file_path=file_path,
                class_line=class_line,
                parent_classes=hierarchy,
                interfaces=reflection.interfaces,
                traits=reflection.traits,
                methods=reflection.methods,
                properties=reflection.properties
            )
        
        # Check for ContainerInjectionInterface
        context.has_container_injection = any(
            "ContainerInjectionInterface" in iface
            for iface in context.interfaces
        )
        
        # Cache the result
        self._context_cache[cache_key] = context
        
        return context
    
    def _find_enclosing_class(
        self,
        lines: list[str],
        cursor_line: int
    ) -> tuple[str, int] | None:
        """
        Find the class declaration that encloses the cursor position.
        
        Uses bracket counting to determine class boundaries.
        
        Args:
            lines: Document lines
            cursor_line: Current cursor line (0-indexed)
        
        Returns:
            Tuple of (class_name, class_declaration_line) or None
        """
        # Pattern for class/interface/trait declaration
        class_pattern = re.compile(
            r"^\s*(final\s+|abstract\s+)?"
            r"(class|interface|trait)\s+"
            r"(\w+)"
        )
        
        # Search backwards from cursor to find class declaration
        brace_count = 0
        in_string = False
        
        for line_num in range(cursor_line, -1, -1):
            line = lines[line_num] if line_num < len(lines) else ""
            
            # Skip counting in strings (simplified)
            for char in reversed(line):
                if char == '}' and not in_string:
                    brace_count += 1
                elif char == '{' and not in_string:
                    brace_count -= 1
            
            # Check for class declaration
            match = class_pattern.search(line)
            if match:
                # If brace_count <= 0, we're inside this class
                if brace_count <= 0:
                    return (match.group(3), line_num)
                # Otherwise, continue searching (nested class case)
                brace_count = 0  # Reset for outer class
        
        return None
    
    def _create_context_from_regex(
        self,
        file_path: Path,
        lines: list[str],
        class_line: int,
        class_name: str
    ) -> ClassContext:
        """
        Create ClassContext using regex parsing when Phpactor fails.
        
        This is a fallback that provides basic information.
        """
        # Try to extract extends/implements from declaration
        declaration = ""
        for i in range(class_line, min(class_line + 5, len(lines))):
            declaration += lines[i]
            if "{" in lines[i]:
                break
        
        # Extract parent class
        extends_match = re.search(r"extends\s+([\w\\]+)", declaration)
        parent = [extends_match.group(1)] if extends_match else []
        
        # Extract interfaces
        implements_match = re.search(r"implements\s+([\w\\,\s]+)", declaration)
        interfaces: list[str] = []
        if implements_match:
            interfaces = [
                i.strip() 
                for i in implements_match.group(1).split(",")
            ]
        
        # Try to determine FQCN from namespace
        namespace = ""
        for line in lines[:class_line]:
            ns_match = re.search(r"namespace\s+([\w\\]+)", line)
            if ns_match:
                namespace = ns_match.group(1)
                break
        
        fqcn = f"{namespace}\\{class_name}" if namespace else class_name
        
        return ClassContext(
            fqcn=fqcn,
            short_name=class_name,
            file_path=file_path,
            class_line=class_line,
            parent_classes=parent,
            interfaces=interfaces
        )
    
    def _position_to_offset(self, lines: list[str], position: Position) -> int:
        """Convert LSP Position to byte offset."""
        offset = 0
        for i in range(position.line):
            if i < len(lines):
                offset += len(lines[i].rstrip('\n')) + 1
        
        if position.line < len(lines):
            offset += min(position.character, len(lines[position.line].rstrip('\n')))
        
        return offset
    
    def _find_project_root(self, file_path: Path) -> Path:
        """Find project root by looking for composer.json."""
        current = file_path.parent
        
        for _ in range(10):
            if (current / "composer.json").exists():
                return current
            if current.parent == current:
                break
            current = current.parent
        
        return file_path.parent
    
    def clear_cache(self) -> None:
        """Clear the context cache."""
        self._context_cache.clear()
```

### Step 4: Implement DrupalContextClassifier

```python
# drupalls/context/drupal_classifier.py

from drupalls.context.class_context import ClassContext
from drupalls.context.types import DrupalClassType


# Mapping of Drupal base classes to class types
DRUPAL_BASE_CLASSES: dict[str, DrupalClassType] = {
    # Controllers
    "Drupal\\Core\\Controller\\ControllerBase": DrupalClassType.CONTROLLER,
    "ControllerBase": DrupalClassType.CONTROLLER,
    
    # Forms
    "Drupal\\Core\\Form\\FormBase": DrupalClassType.FORM,
    "Drupal\\Core\\Form\\ConfigFormBase": DrupalClassType.FORM,
    "Drupal\\Core\\Form\\ConfirmFormBase": DrupalClassType.FORM,
    "FormBase": DrupalClassType.FORM,
    "ConfigFormBase": DrupalClassType.FORM,
    
    # Entities
    "Drupal\\Core\\Entity\\ContentEntityBase": DrupalClassType.ENTITY,
    "Drupal\\Core\\Entity\\ConfigEntityBase": DrupalClassType.ENTITY,
    "Drupal\\Core\\Entity\\EntityBase": DrupalClassType.ENTITY,
    "ContentEntityBase": DrupalClassType.ENTITY,
    "ConfigEntityBase": DrupalClassType.ENTITY,
    
    # Plugins
    "Drupal\\Core\\Plugin\\PluginBase": DrupalClassType.PLUGIN,
    "Drupal\\Component\\Plugin\\PluginBase": DrupalClassType.PLUGIN,
    "PluginBase": DrupalClassType.PLUGIN,
    
    # Blocks (also plugins)
    "Drupal\\Core\\Block\\BlockBase": DrupalClassType.BLOCK,
    "BlockBase": DrupalClassType.BLOCK,
    
    # Field formatters/widgets
    "Drupal\\Core\\Field\\FormatterBase": DrupalClassType.FIELD_FORMATTER,
    "Drupal\\Core\\Field\\WidgetBase": DrupalClassType.FIELD_WIDGET,
    "FormatterBase": DrupalClassType.FIELD_FORMATTER,
    "WidgetBase": DrupalClassType.FIELD_WIDGET,
    
    # Migrations
    "Drupal\\migrate\\Plugin\\migrate\\source\\SourcePluginBase": DrupalClassType.MIGRATION,
    "Drupal\\migrate_drupal\\Plugin\\migrate\\source\\DrupalSqlBase": DrupalClassType.MIGRATION,
    
    # Queue workers
    "Drupal\\Core\\Queue\\QueueWorkerBase": DrupalClassType.QUEUE_WORKER,
    "QueueWorkerBase": DrupalClassType.QUEUE_WORKER,
    
    # Constraints
    "Symfony\\Component\\Validator\\Constraint": DrupalClassType.CONSTRAINT,
    "Drupal\\Core\\Validation\\Plugin\\Validation\\Constraint\\ConstraintBase": DrupalClassType.CONSTRAINT,
}

# Mapping of interfaces to class types
DRUPAL_INTERFACES: dict[str, DrupalClassType] = {
    "Symfony\\Component\\EventDispatcher\\EventSubscriberInterface": DrupalClassType.EVENT_SUBSCRIBER,
    "EventSubscriberInterface": DrupalClassType.EVENT_SUBSCRIBER,
    
    "Drupal\\Core\\Routing\\Access\\AccessInterface": DrupalClassType.ACCESS_CHECKER,
    "AccessInterface": DrupalClassType.ACCESS_CHECKER,
    
    "Drupal\\Core\\Form\\FormInterface": DrupalClassType.FORM,
    "FormInterface": DrupalClassType.FORM,
    
    "Drupal\\Core\\Entity\\EntityInterface": DrupalClassType.ENTITY,
    "EntityInterface": DrupalClassType.ENTITY,
    
    "Drupal\\Core\\Block\\BlockPluginInterface": DrupalClassType.BLOCK,
    "BlockPluginInterface": DrupalClassType.BLOCK,
}


class DrupalContextClassifier:
    """
    Classifies PHP classes into Drupal construct types.
    
    Uses parent class inheritance and interface implementation
    to determine what kind of Drupal construct a class represents.
    """
    
    def classify(self, context: ClassContext) -> DrupalClassType:
        """
        Classify a class context into a Drupal type.
        
        Priority:
        1. Check parent classes (more specific wins)
        2. Check interfaces
        3. Check namespace patterns
        4. Return UNKNOWN
        
        Args:
            context: ClassContext with parent/interface info
        
        Returns:
            DrupalClassType classification
        """
        # Check parent classes first (includes full hierarchy)
        for parent in context.parent_classes:
            # Check both full and short names
            if parent in DRUPAL_BASE_CLASSES:
                context.drupal_type = DRUPAL_BASE_CLASSES[parent]
                return context.drupal_type
            
            # Check short name
            short_parent = parent.split("\\")[-1]
            if short_parent in DRUPAL_BASE_CLASSES:
                context.drupal_type = DRUPAL_BASE_CLASSES[short_parent]
                return context.drupal_type
        
        # Check interfaces
        for interface in context.interfaces:
            if interface in DRUPAL_INTERFACES:
                context.drupal_type = DRUPAL_INTERFACES[interface]
                return context.drupal_type
            
            short_interface = interface.split("\\")[-1]
            if short_interface in DRUPAL_INTERFACES:
                context.drupal_type = DRUPAL_INTERFACES[short_interface]
                return context.drupal_type
        
        # Check namespace patterns as fallback
        drupal_type = self._classify_by_namespace(context.fqcn)
        context.drupal_type = drupal_type
        return drupal_type
    
    def _classify_by_namespace(self, fqcn: str) -> DrupalClassType:
        """
        Classify based on namespace patterns.
        
        This is a fallback for when parent class info isn't available.
        """
        fqcn_lower = fqcn.lower()
        
        patterns: dict[str, DrupalClassType] = {
            "\\controller\\": DrupalClassType.CONTROLLER,
            "\\form\\": DrupalClassType.FORM,
            "\\plugin\\block\\": DrupalClassType.BLOCK,
            "\\plugin\\field\\formatter\\": DrupalClassType.FIELD_FORMATTER,
            "\\plugin\\field\\widget\\": DrupalClassType.FIELD_WIDGET,
            "\\plugin\\migrate\\": DrupalClassType.MIGRATION,
            "\\plugin\\queueworker\\": DrupalClassType.QUEUE_WORKER,
            "\\plugin\\": DrupalClassType.PLUGIN,
            "\\entity\\": DrupalClassType.ENTITY,
            "\\eventsubscriber\\": DrupalClassType.EVENT_SUBSCRIBER,
            "\\access\\": DrupalClassType.ACCESS_CHECKER,
        }
        
        for pattern, dtype in patterns.items():
            if pattern in fqcn_lower:
                return dtype
        
        return DrupalClassType.UNKNOWN
    
    def is_service_class(self, context: ClassContext) -> bool:
        """
        Determine if the class is likely a Drupal service.
        
        Services typically:
        - Implement ContainerInjectionInterface
        - Have a create() method
        - Are registered in services.yml
        """
        # ContainerInjectionInterface is a strong indicator
        if context.has_container_injection:
            return True
        
        # create() static method is another indicator
        if "create" in context.methods:
            return True
        
        # Some types are always services
        service_types = {
            DrupalClassType.EVENT_SUBSCRIBER,
            DrupalClassType.ACCESS_CHECKER,
        }
        
        return context.drupal_type in service_types
```

### Step 5: Refactor TypeChecker

Simplify the TypeChecker to use the new components:

```python
# drupalls/lsp/type_checker.py

from lsprotocol.types import Position

from drupalls.context.class_context_detector import ClassContextDetector
from drupalls.context.drupal_classifier import DrupalContextClassifier
from drupalls.context.class_context import ClassContext
from drupalls.phpactor.client import PhpactorClient


class TypeChecker:
    """
    Unified type checker using context-aware Phpactor integration.
    
    This refactored class delegates to specialized components
    for cleaner separation of concerns.
    """
    
    def __init__(self, phpactor_client: PhpactorClient | None = None):
        """
        Initialize TypeChecker.
        
        Args:
            phpactor_client: Optional PhpactorClient instance.
                           Creates one if not provided.
        """
        if phpactor_client is None:
            phpactor_client = PhpactorClient()
        
        self.phpactor = phpactor_client
        self.context_detector = ClassContextDetector(phpactor_client)
        self.classifier = DrupalContextClassifier()
        
        # Cache for variable type lookups
        self._type_cache: dict[tuple, str | None] = {}
    
    async def get_class_context(
        self,
        uri: str,
        position: Position,
        doc_lines: list[str] | None = None
    ) -> ClassContext | None:
        """
        Get the classified class context at a position.
        
        Args:
            uri: Document URI
            position: Cursor position
            doc_lines: Optional document lines
        
        Returns:
            ClassContext with drupal_type set, or None
        """
        context = await self.context_detector.get_class_at_position(
            uri, position, doc_lines
        )
        
        if context:
            self.classifier.classify(context)
        
        return context
    
    async def is_container_variable(
        self,
        doc,
        line: str,
        position: Position
    ) -> bool:
        """
        Check if the variable in ->get() call is a ContainerInterface.
        
        Maintains backward compatibility with existing capability code.
        
        Args:
            doc: Document object with uri and lines
            line: Current line text
            position: Cursor position
        
        Returns:
            True if variable is ContainerInterface type
        """
        var_name = self._extract_variable_from_get_call(line, position)
        if not var_name:
            return False
        
        cache_key = (doc.uri, position.line, var_name)
        
        if cache_key in self._type_cache:
            var_type = self._type_cache[cache_key]
        else:
            var_type = await self._query_variable_type(doc, position)
            self._type_cache[cache_key] = var_type
        
        if not var_type:
            # Fallback heuristics
            if var_name.lower() == "container":
                return True
            return False
        
        return self._is_container_interface(var_type)
    
    async def _query_variable_type(
        self,
        doc,
        position: Position
    ) -> str | None:
        """Query Phpactor for variable type at position."""
        from pathlib import Path
        
        file_path = Path(doc.uri.replace("file://", ""))
        offset = self._position_to_offset(doc.lines, position)
        working_dir = self._find_project_root(file_path)
        
        type_info = await self.phpactor.offset_info(
            file_path, offset, working_dir
        )
        
        return type_info.type_name if type_info else None
    
    def _extract_variable_from_get_call(
        self,
        line: str,
        position: Position
    ) -> str | None:
        """Extract variable name from ->get() call context."""
        import re
        
        get_pos = line.rfind("->get(", 0, position.character + 1)
        if get_pos == -1:
            return None
        
        # Find variable before ->get(
        before_get = line[:get_pos]
        
        # Match variable patterns
        patterns = [
            r'\$(\w+)\s*$',           # $var->get(
            r'->(\w+)\s*$',           # $this->var->get(
            r'(\w+)\(\)\s*$',         # getContainer()->get(
        ]
        
        for pattern in patterns:
            match = re.search(pattern, before_get)
            if match:
                return match.group(1)
        
        return None
    
    def _is_container_interface(self, type_str: str) -> bool:
        """Check if type represents a ContainerInterface."""
        container_types = [
            "ContainerInterface",
            "Symfony\\Component\\DependencyInjection\\ContainerInterface",
            "Psr\\Container\\ContainerInterface",
            "Drupal\\Core\\DependencyInjection\\ContainerInterface",
        ]
        
        type_lower = type_str.lower()
        return any(ct.lower() in type_lower for ct in container_types)
    
    def _position_to_offset(self, lines: list[str], position: Position) -> int:
        """Convert Position to byte offset."""
        offset = 0
        for i in range(position.line):
            if i < len(lines):
                offset += len(lines[i].rstrip('\n')) + 1
        
        if position.line < len(lines):
            offset += min(position.character, len(lines[position.line].rstrip('\n')))
        
        return offset
    
    def _find_project_root(self, file_path) -> 'Path':
        """Find project root containing composer.json."""
        from pathlib import Path
        
        current = file_path.parent if hasattr(file_path, 'parent') else Path(file_path).parent
        
        for _ in range(10):
            if (current / "composer.json").exists():
                return current
            if current.parent == current:
                break
            current = current.parent
        
        return file_path.parent if hasattr(file_path, 'parent') else Path(file_path).parent
    
    def clear_cache(self) -> None:
        """Clear all caches."""
        self._type_cache.clear()
        self.context_detector.clear_cache()
```

### Step 6: Server Integration

```python
# drupalls/lsp/server.py (integration changes)

from drupalls.phpactor.client import PhpactorClient
from drupalls.lsp.type_checker import TypeChecker


class DrupalLanguageServer:
    """Main language server class."""
    
    def __init__(self):
        # ... existing init ...
        
        # Initialize Phpactor integration
        self.phpactor_client: PhpactorClient | None = None
        self.type_checker: TypeChecker | None = None
    
    async def initialize(self, params):
        # ... existing initialization ...
        
        # Initialize Phpactor client
        try:
            self.phpactor_client = PhpactorClient()
            if self.phpactor_client.is_available():
                self.type_checker = TypeChecker(self.phpactor_client)
            else:
                # Fallback: TypeChecker with limited functionality
                self.type_checker = TypeChecker()
        except Exception:
            self.type_checker = TypeChecker()
        
        # ... rest of initialization ...
```

## Usage Examples

### In Completion Capability

```python
# drupalls/lsp/capabilities/services_capabilities.py

async def _is_service_pattern(server, params) -> bool:
    """Check if we should provide service completion."""
    doc = server.workspace.get_text_document(params.text_document.uri)
    line = doc.lines[params.position.line]
    
    # Quick pattern check first
    if "::service(" in line or "getContainer()->get(" in line:
        return True
    
    # Use type checker for ->get() calls
    if "->get(" in line and server.type_checker:
        return await server.type_checker.is_container_variable(
            doc, line, params.position
        )
    
    return False


async def provide_context_aware_completion(server, params):
    """Provide completions based on class context."""
    if not server.type_checker:
        return []
    
    doc = server.workspace.get_text_document(params.text_document.uri)
    
    context = await server.type_checker.get_class_context(
        params.text_document.uri,
        params.position,
        doc.lines
    )
    
    if not context:
        return []
    
    completions = []
    
    # Controller-specific completions
    if context.drupal_type == DrupalClassType.CONTROLLER:
        # Suggest common controller methods
        if not context.has_method("create"):
            completions.append(create_create_method_snippet())
    
    # Form-specific completions
    elif context.drupal_type == DrupalClassType.FORM:
        if not context.has_method("getFormId"):
            completions.append(create_form_id_snippet())
        if not context.has_method("buildForm"):
            completions.append(create_build_form_snippet())
    
    # Plugin-specific completions
    elif context.drupal_type == DrupalClassType.PLUGIN:
        # Suggest plugin annotation if missing
        pass
    
    return completions
```

### Getting Parent Classes

```python
# Example: Check if class can use dependency injection

async def can_use_dependency_injection(server, uri, position):
    """Check if the current class supports DI."""
    context = await server.type_checker.get_class_context(uri, position)
    
    if not context:
        return False
    
    # Classes with ContainerInjectionInterface support DI
    if context.has_container_injection:
        return True
    
    # Controllers, Forms, Plugins support DI
    di_types = {
        DrupalClassType.CONTROLLER,
        DrupalClassType.FORM,
        DrupalClassType.PLUGIN,
        DrupalClassType.BLOCK,
    }
    
    return context.drupal_type in di_types
```

## Edge Cases

### Nested Classes

PHP 8.4+ supports nested classes. The `_find_enclosing_class()` method uses brace counting to handle this:

```php
class Outer {
    public function method() {
        // Cursor here
        $anon = new class extends Inner {
            // Not this class
        };
    }
}
```

### Anonymous Classes

Anonymous classes don't have a name and are handled specially:

```python
def _find_enclosing_class(self, lines, cursor_line):
    # Pattern also matches "new class"
    anon_pattern = re.compile(r"new\s+class\b")
    # ...
```

### Traits

Traits are detected and included in the context:

```php
trait MyTrait {
    // Context will have this as the class
}

class MyClass {
    use MyTrait;
    // Context will be MyClass, with MyTrait in traits list
}
```

### Files Without Classes

Function-only files or procedural code return `None`:

```python
context = await detector.get_class_at_position(uri, position)
if context is None:
    # Not inside a class - handle accordingly
    pass
```

## Testing

### Unit Tests

```python
# tests/test_class_context_detector.py

import pytest
from pathlib import Path
from lsprotocol.types import Position

from drupalls.context.class_context_detector import ClassContextDetector
from drupalls.context.types import DrupalClassType
from drupalls.phpactor.client import PhpactorClient


class MockPhpactorClient(PhpactorClient):
    """Mock client for testing without Phpactor."""
    
    def __init__(self):
        self.drupalls_root = Path("/mock")
        self.phpactor_bin = Path("/mock/bin/phpactor")
    
    async def class_reflect(self, *args, **kwargs):
        return None  # Force regex fallback
    
    async def get_class_hierarchy(self, *args, **kwargs):
        return []


@pytest.fixture
def detector():
    return ClassContextDetector(MockPhpactorClient())


@pytest.mark.asyncio
async def test_find_controller_class(detector):
    """Test detecting a controller class."""
    lines = [
        "<?php\n",
        "\n",
        "namespace Drupal\\mymodule\\Controller;\n",
        "\n",
        "use Drupal\\Core\\Controller\\ControllerBase;\n",
        "\n",
        "class MyController extends ControllerBase {\n",
        "    public function build() {\n",
        "        // cursor here\n",
        "    }\n",
        "}\n",
    ]
    
    # Create a temporary file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.php', delete=False) as f:
        f.writelines(lines)
        file_path = f.name
    
    try:
        context = await detector.get_class_at_position(
            f"file://{file_path}",
            Position(line=8, character=10),
            lines
        )
        
        assert context is not None
        assert context.short_name == "MyController"
        assert "ControllerBase" in context.parent_classes[0]
    finally:
        Path(file_path).unlink()


@pytest.mark.asyncio
async def test_find_form_class(detector):
    """Test detecting a form class."""
    lines = [
        "<?php\n",
        "namespace Drupal\\mymodule\\Form;\n",
        "class MyForm extends FormBase implements FormInterface {\n",
        "}\n",
    ]
    
    # ... similar test structure
```

### Integration Tests

```python
# tests/test_phpactor_integration.py

import pytest
from drupalls.phpactor.client import PhpactorClient


@pytest.fixture
def phpactor_client():
    client = PhpactorClient()
    if not client.is_available():
        pytest.skip("Phpactor not available")
    return client


@pytest.mark.asyncio
async def test_real_phpactor_offset_info(phpactor_client, tmp_path):
    """Test real Phpactor integration."""
    # Create a test PHP file
    php_file = tmp_path / "test.php"
    php_file.write_text("""<?php
namespace Test;

class TestClass {
    private ContainerInterface $container;
}
""")
    
    result = await phpactor_client.offset_info(php_file, 50)
    # Assert based on actual Phpactor behavior
```

## Performance Considerations

### Caching Strategy

Three levels of caching are implemented:

1. **Reflection Cache** (PhpactorClient): Caches class reflection results
2. **Context Cache** (ClassContextDetector): Caches by (uri, line)
3. **Type Cache** (TypeChecker): Caches variable type lookups

```python
# Cache invalidation on document change
async def did_change(self, params):
    uri = params.text_document.uri
    
    # Clear context cache for this file
    self.type_checker.context_detector._context_cache = {
        k: v for k, v in self.type_checker.context_detector._context_cache.items()
        if k[0] != uri
    }
    
    # Clear type cache for this file
    self.type_checker._type_cache = {
        k: v for k, v in self.type_checker._type_cache.items()
        if k[0] != uri
    }
```

### Async Processing

All Phpactor calls are async to avoid blocking the LSP event loop:

```python
# Use asyncio.gather for parallel queries
async def get_multiple_contexts(uris, positions):
    tasks = [
        detector.get_class_at_position(uri, pos)
        for uri, pos in zip(uris, positions)
    ]
    return await asyncio.gather(*tasks)
```

## Migration Guide

### From Current Implementation

1. **Replace imports**:
   ```python
   # Before
   from drupalls.lsp.phpactor_integration import TypeChecker
   
   # After
   from drupalls.lsp.type_checker import TypeChecker
   ```

2. **Update server initialization**: See Step 6 above

3. **Existing `is_container_variable()` calls**: No changes needed - API is backward compatible

4. **New context-aware features**: Use `get_class_context()` method

### Deprecation Path

The old `phpactor_integration.py` and `phpactor_cli.py` files should be:

1. Marked as deprecated with warnings
2. Kept for one release cycle
3. Removed in the following release

## Future Enhancements

### Plugin Annotation Detection

Detect `@Block`, `@Action`, etc. annotations:

```python
def detect_plugin_annotation(lines: list[str], class_line: int) -> str | None:
    """Detect plugin annotation above class declaration."""
    for i in range(class_line - 1, max(0, class_line - 20), -1):
        if "@" in lines[i] and "Plugin" in lines[i]:
            # Parse annotation
            pass
```

### Service Definition Lookup

Cross-reference with services.yml cache:

```python
async def is_registered_service(context: ClassContext, services_cache) -> bool:
    """Check if class is registered as a service."""
    return any(
        s.class_name == context.fqcn
        for s in services_cache.get_all().values()
    )
```

### Method Parameter Type Detection

Detect injected service types in constructor:

```python
async def get_injected_services(context: ClassContext) -> list[str]:
    """Get list of services injected via constructor."""
    # Parse __construct parameters
    # Cross-reference with container types
    pass
```

## References

- **Phpactor Documentation**: https://phpactor.readthedocs.io/
- **Phpactor RPC**: https://phpactor.readthedocs.io/en/master/reference/rpc.html
- **Drupal Base Classes**: https://api.drupal.org/api/drupal/core%21lib%21Drupal/
- **LSP Specification**: https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/
- **Previous Implementation Docs**:
  - `IMPLEMENTATION-013-INTEGRATING_PHPactor_CLI_AS_DEPENDENCY.md`
  - `IMPLEMENTATION-015-INTEGRATING_PHPactor_CLI_TYPE_CHECKING.md`
