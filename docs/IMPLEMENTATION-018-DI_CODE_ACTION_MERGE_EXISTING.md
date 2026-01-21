# DI Code Action: Merge with Existing Code

## Overview

This implementation guide fixes the DI Code Action feature (IMPLEMENTATION-017) to properly **merge** new dependency injection code with existing class structures instead of blindly inserting new code that creates duplicates and corrupts the file.

### Problem Statement

The current DI Code Action has critical bugs when applied to files that already have:
- Existing `use` statements
- Existing `__construct()` method with parameters
- Existing `create()` method with container gets
- Existing properties with docstrings

**Current Behavior (BROKEN):**
- Adds duplicate `use` statements
- Creates new `__construct()` and `create()` methods instead of merging
- Inserts properties without docstrings
- Places code in wrong locations, corrupting the file structure

**Required Behavior:**
- Check for existing `use` statements before adding new ones
- Merge new parameters into existing `__construct()`
- Merge new container gets into existing `create()`
- Insert properties with proper docstrings
- Place new properties after class declaration/traits, before existing properties

## Real-World Example

### Before (Input File)

```php
<?php

namespace Drupal\user_revision_cp\Controller;

use Drupal\Core\Link;
use Drupal\Core\Controller\ControllerBase;
use Drupal\Core\DependencyInjection\ContainerInjectionInterface;
use Drupal\Core\Datetime\DateFormatter;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Drupal\user\UserInterface;
use Drupal\Component\Utility\Xss;
use Drupal\Core\Url;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;
use Drupal\user_revision_cp\Access\UserRevisionAccessCheck;

/**
 * Returns responses for User revision routes.
 */
class UserController extends ControllerBase implements ContainerInjectionInterface {

  /**
   * The date formatter service.
   *
   * @var \Drupal\Core\Datetime\DateFormatter
   */
  protected $dateFormatter;

  /**
   * The access_check.user.revision service.
   *
   * @var \Drupal\user_revision_cp\Access\UserRevisionAccessCheck
   */
  protected $userRevisionAccessCheck;

  /**
   * Constructs a UserController object.
   *
   * @param \Drupal\Core\Datetime\DateFormatter $date_formatter
   *   The date formatter service.
   */
  public function __construct(DateFormatter $date_formatter,
                              UserRevisionAccessCheck $accessCheck ) {
    $this->dateFormatter = $date_formatter;
    $this->userRevisionAccessCheck = $accessCheck;
    $this->entityTypeManager();
  }

  /**
   * {@inheritdoc}
   */
  public static function create(ContainerInterface $container) {
    return new static(
      $container->get('date.formatter'),
      $container->get('access_check.user.revision')
    );
  }

  public function revisionOverview(UserInterface $user) {
    // ...
    'username' => \Drupal::service('renderer')->render($username),
    // ...
  }

  public function revisionShow($user, $user_revision) {
    // ...
    $a = \Drupal::service("entity.repository");
    // ...
  }
}
```

**Static calls to convert:**
- Line 111: `\Drupal::service('renderer')`
- Line 195: `\Drupal::service("entity.repository")`

### Expected Output (Correct)

```php
<?php

namespace Drupal\user_revision_cp\Controller;

use Drupal\Core\Entity\EntityRepositoryInterface;
use Drupal\Core\Link;
use Drupal\Core\Controller\ControllerBase;
use Drupal\Core\DependencyInjection\ContainerInjectionInterface;
use Drupal\Core\Datetime\DateFormatter;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Drupal\user\UserInterface;
use Drupal\Component\Utility\Xss;
use Drupal\Core\Url;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;
use Drupal\user_revision_cp\Access\UserRevisionAccessCheck;
use Drupal\Core\Render\RendererInterface;

/**
 * Returns responses for User revision routes.
 */
class UserController extends ControllerBase implements ContainerInjectionInterface {

  /**
   * The renderer service.
   *
   * @var \Drupal\Core\Render\RendererInterface
   */
  protected RendererInterface $renderer;

  /**
   * The entity repository service.
   *
   * @var \Drupal\Core\Entity\EntityRepositoryInterface
   */
  protected EntityRepositoryInterface $entityRepository;

  /**
   * The date formatter service.
   *
   * @var \Drupal\Core\Datetime\DateFormatter
   */
  protected $dateFormatter;

  /**
   * The access_check.user.revision service.
   *
   * @var \Drupal\user_revision_cp\Access\UserRevisionAccessCheck
   */
  protected $userRevisionAccessCheck;

  /**
   * Constructs a UserController object.
   *
   * @param \Drupal\Core\Datetime\DateFormatter $date_formatter
   *   The date formatter service.
   * @param \Drupal\user_revision_cp\Access\UserRevisionAccessCheck $accessCheck
   *   The user revision access check service.
   * @param \Drupal\Core\Render\RendererInterface $renderer
   *   The renderer service.
   * @param \Drupal\Core\Entity\EntityRepositoryInterface $entity_repository
   *   The entity repository service.
   */
  public function __construct(
    DateFormatter $date_formatter,
    UserRevisionAccessCheck $accessCheck,
    RendererInterface $renderer,
    EntityRepositoryInterface $entity_repository
  ) {
    $this->dateFormatter = $date_formatter;
    $this->userRevisionAccessCheck = $accessCheck;
    $this->entityTypeManager();
    $this->renderer = $renderer;
    $this->entityRepository = $entity_repository;
  }

  /**
   * {@inheritdoc}
   */
  public static function create(ContainerInterface $container) {
    return new static(
      $container->get('date.formatter'),
      $container->get('access_check.user.revision'),
      $container->get('renderer'),
      $container->get('entity.repository')
    );
  }

  public function revisionOverview(UserInterface $user) {
    // ...
    'username' => $this->renderer->render($username),
    // ...
  }

  public function revisionShow($user, $user_revision) {
    // ...
    $a = $this->entityRepository;
    // ...
  }
}
```

### Key Differences

| Aspect | Before | After |
|--------|--------|-------|
| Use statements | 10 statements | 12 statements (2 new, no duplicates) |
| Properties | 2 | 4 (2 new with docstrings) |
| Constructor params | 2 | 4 (2 new appended) |
| Create container gets | 2 | 4 (2 new appended) |
| Static calls | 2 | 0 (replaced with `$this->`) |

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DI Code Action Flow                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐     ┌───────────────────────┐     ┌────────────────┐  │
│  │ StaticCallDetector│────▶│   PhpClassAnalyzer    │────▶│ DIStrategy     │  │
│  │                   │     │        (NEW)          │     │                │  │
│  │ Finds:            │     │ Extracts:             │     │ Generates:     │  │
│  │ - \Drupal::service│     │ - Existing use stmts  │     │ - Use edits    │  │
│  │ - \Drupal::xxx()  │     │ - Existing properties │     │ - Property edits│ │
│  │ - container->get  │     │ - __construct() info  │     │ - Constructor  │  │
│  └──────────────────┘     │ - create() info       │     │ - create()     │  │
│                            │ - Class structure     │     │ - Replacements │  │
│                            └───────────────────────┘     └────────────────┘  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    Edit Generation Strategy                           │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │                                                                       │   │
│  │  1. USE STATEMENTS: Insert only new ones at use_section_end_line     │   │
│  │  2. PROPERTIES: Insert with docstrings after class/traits            │   │
│  │  3. CONSTRUCTOR: Replace entire method with merged version           │   │
│  │  4. CREATE(): Replace entire method with merged version              │   │
│  │  5. STATIC CALLS: Replace each with $this->propertyName              │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. User triggers code action on PHP file
         ↓
2. StaticCallDetector finds static Drupal calls
         ↓
3. PhpClassAnalyzer extracts existing class structure:
   - use statements (with line numbers)
   - class declaration line
   - trait usage lines
   - property declarations (with docstrings)
   - __construct() location, params, body
   - create() location, container gets
         ↓
4. DIStrategy generates edits:
   - Filter out duplicate use statements
   - Generate properties with docstrings
   - Merge constructor (existing + new params)
   - Merge create (existing + new gets)
   - Replace static calls
         ↓
5. LSP applies TextEdits to document
```

## Implementation Guide

### Step 1: Create PhpClassAnalyzer

Create `drupalls/lsp/capabilities/di_refactoring/php_class_analyzer.py`:

```python
"""
PHP class structure analyzer for DI refactoring.

File: drupalls/lsp/capabilities/di_refactoring/php_class_analyzer.py
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ConstructorInfo:
    """Information about an existing __construct() method."""
    
    start_line: int  # Line with "public function __construct"
    end_line: int    # Line with closing "}"
    params: list[tuple[str, str | None]]  # [(param_name, type_hint), ...]
    body_lines: list[str]  # Lines inside constructor body
    docblock_start: int | None  # Line where docblock starts
    docblock_end: int | None    # Line where docblock ends


@dataclass
class CreateMethodInfo:
    """Information about an existing create() method."""
    
    start_line: int  # Line with "public static function create"
    end_line: int    # Line with closing "}"
    container_gets: list[str]  # Service IDs from $container->get('...')
    docblock_start: int | None
    docblock_end: int | None


@dataclass
class PropertyInfo:
    """Information about an existing property."""
    
    name: str
    line: int
    type_hint: str | None
    has_docblock: bool
    docblock_start: int | None
    docblock_end: int | None


@dataclass
class PhpClassInfo:
    """Complete analyzed PHP class structure."""
    
    # Use statements
    use_statements: dict[str, int] = field(default_factory=dict)  # fqcn -> line
    use_section_start: int = 0
    use_section_end: int = 0
    
    # Class declaration
    class_line: int = 0
    class_name: str = ""
    extends: str | None = None
    implements: list[str] = field(default_factory=list)
    
    # Trait usage inside class
    trait_use_lines: list[int] = field(default_factory=list)
    
    # Properties
    properties: dict[str, PropertyInfo] = field(default_factory=dict)
    first_property_line: int | None = None
    
    # Constructor
    constructor: ConstructorInfo | None = None
    
    # Create method
    create_method: CreateMethodInfo | None = None


class PhpClassAnalyzer:
    """Analyzes PHP class structure for DI refactoring."""
    
    # Patterns
    USE_PATTERN = re.compile(r"^\s*use\s+([\w\\]+)(?:\s+as\s+\w+)?;")
    CLASS_PATTERN = re.compile(
        r"^\s*(final\s+|abstract\s+)?(class|interface|trait)\s+(\w+)"
        r"(?:\s+extends\s+([\w\\]+))?"
        r"(?:\s+implements\s+([\w\\,\s]+))?"
    )
    TRAIT_USE_PATTERN = re.compile(r"^\s+use\s+([\w\\]+);")
    PROPERTY_PATTERN = re.compile(
        r"^\s+(protected|private|public)\s+"
        r"(?:([\w\\]+)\s+)?"
        r"\$(\w+)"
    )
    CONSTRUCTOR_PATTERN = re.compile(
        r"^\s+public\s+function\s+__construct\s*\("
    )
    CREATE_PATTERN = re.compile(
        r"^\s+public\s+static\s+function\s+create\s*\("
    )
    CONTAINER_GET_PATTERN = re.compile(
        r"\$container->get\(\s*['\"]([^'\"]+)['\"]\s*\)"
    )
    DOCBLOCK_START = re.compile(r"^\s*/\*\*")
    DOCBLOCK_END = re.compile(r"^\s*\*/")
    
    def analyze(self, content: str) -> PhpClassInfo:
        """Analyze PHP file content and return class structure info."""
        info = PhpClassInfo()
        lines = content.split("\n")
        
        self._parse_use_statements(lines, info)
        self._parse_class_declaration(lines, info)
        self._parse_class_body(lines, info)
        
        return info
    
    def _parse_use_statements(
        self, lines: list[str], info: PhpClassInfo
    ) -> None:
        """Parse use statements at file level."""
        in_use_section = False
        
        for i, line in enumerate(lines):
            # Skip until we find first use statement
            match = self.USE_PATTERN.match(line)
            if match:
                if not in_use_section:
                    info.use_section_start = i
                    in_use_section = True
                
                fqcn = match.group(1)
                info.use_statements[fqcn] = i
                info.use_section_end = i + 1
            
            # Stop at class declaration
            if self.CLASS_PATTERN.match(line):
                break
    
    def _parse_class_declaration(
        self, lines: list[str], info: PhpClassInfo
    ) -> None:
        """Parse class declaration line."""
        for i, line in enumerate(lines):
            match = self.CLASS_PATTERN.match(line)
            if match:
                info.class_line = i
                info.class_name = match.group(3)
                info.extends = match.group(4)
                
                implements_str = match.group(5)
                if implements_str:
                    info.implements = [
                        impl.strip() 
                        for impl in implements_str.split(",")
                    ]
                break
    
    def _parse_class_body(
        self, lines: list[str], info: PhpClassInfo
    ) -> None:
        """Parse class body: traits, properties, constructor, create."""
        if info.class_line == 0:
            return
        
        # Track docblock for properties/methods
        current_docblock_start: int | None = None
        current_docblock_end: int | None = None
        
        i = info.class_line + 1
        while i < len(lines):
            line = lines[i]
            
            # Track docblocks
            if self.DOCBLOCK_START.match(line):
                current_docblock_start = i
                current_docblock_end = None
            elif self.DOCBLOCK_END.match(line):
                current_docblock_end = i
            
            # Trait use statements inside class
            trait_match = self.TRAIT_USE_PATTERN.match(line)
            if trait_match:
                info.trait_use_lines.append(i)
                i += 1
                continue
            
            # Properties
            prop_match = self.PROPERTY_PATTERN.match(line)
            if prop_match:
                prop_name = prop_match.group(3)
                prop_type = prop_match.group(2)
                
                prop_info = PropertyInfo(
                    name=prop_name,
                    line=i,
                    type_hint=prop_type,
                    has_docblock=current_docblock_end is not None,
                    docblock_start=current_docblock_start,
                    docblock_end=current_docblock_end,
                )
                info.properties[prop_name] = prop_info
                
                if info.first_property_line is None:
                    info.first_property_line = (
                        current_docblock_start 
                        if current_docblock_start is not None 
                        else i
                    )
                
                # Reset docblock tracking
                current_docblock_start = None
                current_docblock_end = None
                i += 1
                continue
            
            # Constructor
            if self.CONSTRUCTOR_PATTERN.match(line):
                info.constructor = self._parse_constructor(
                    lines, i, current_docblock_start, current_docblock_end
                )
                i = info.constructor.end_line + 1
                current_docblock_start = None
                current_docblock_end = None
                continue
            
            # Create method
            if self.CREATE_PATTERN.match(line):
                info.create_method = self._parse_create_method(
                    lines, i, current_docblock_start, current_docblock_end
                )
                i = info.create_method.end_line + 1
                current_docblock_start = None
                current_docblock_end = None
                continue
            
            # Reset docblock if we hit non-docblock, non-empty line
            if line.strip() and not line.strip().startswith("*"):
                if not self.DOCBLOCK_START.match(line):
                    current_docblock_start = None
                    current_docblock_end = None
            
            i += 1
    
    def _parse_constructor(
        self,
        lines: list[str],
        start_line: int,
        docblock_start: int | None,
        docblock_end: int | None,
    ) -> ConstructorInfo:
        """Parse __construct() method."""
        # Find method end by counting braces
        brace_count = 0
        end_line = start_line
        params: list[tuple[str, str | None]] = []
        body_lines: list[str] = []
        in_body = False
        
        # Extract parameters from declaration
        param_text = ""
        i = start_line
        while i < len(lines):
            param_text += lines[i]
            if ")" in lines[i]:
                break
            i += 1
        
        # Parse parameters
        param_section = re.search(r"\((.*)\)", param_text, re.DOTALL)
        if param_section:
            param_str = param_section.group(1)
            for param in param_str.split(","):
                param = param.strip()
                if not param:
                    continue
                
                # Match: TypeHint $name or $name
                param_match = re.match(
                    r"(?:([\w\\]+)\s+)?(\$\w+)", param
                )
                if param_match:
                    type_hint = param_match.group(1)
                    name = param_match.group(2).lstrip("$")
                    params.append((name, type_hint))
        
        # Find method body and end
        for i in range(start_line, len(lines)):
            line = lines[i]
            
            if "{" in line:
                brace_count += line.count("{")
                if not in_body:
                    in_body = True
            
            if "}" in line:
                brace_count -= line.count("}")
            
            if in_body and brace_count == 0:
                end_line = i
                break
            
            if in_body:
                body_lines.append(line)
        
        return ConstructorInfo(
            start_line=start_line,
            end_line=end_line,
            params=params,
            body_lines=body_lines,
            docblock_start=docblock_start,
            docblock_end=docblock_end,
        )
    
    def _parse_create_method(
        self,
        lines: list[str],
        start_line: int,
        docblock_start: int | None,
        docblock_end: int | None,
    ) -> CreateMethodInfo:
        """Parse create() method."""
        brace_count = 0
        end_line = start_line
        container_gets: list[str] = []
        
        for i in range(start_line, len(lines)):
            line = lines[i]
            
            # Extract container->get calls
            for match in self.CONTAINER_GET_PATTERN.finditer(line):
                container_gets.append(match.group(1))
            
            if "{" in line:
                brace_count += line.count("{")
            
            if "}" in line:
                brace_count -= line.count("}")
            
            if brace_count > 0 and brace_count == line.count("}"):
                end_line = i
                break
        
        return CreateMethodInfo(
            start_line=start_line,
            end_line=end_line,
            container_gets=container_gets,
            docblock_start=docblock_start,
            docblock_end=docblock_end,
        )
    
    def get_property_insert_line(self, info: PhpClassInfo) -> int:
        """
        Get the line where new properties should be inserted.
        
        Priority:
        1. After last trait use statement
        2. After class declaration opening brace
        3. Before first existing property
        """
        if info.trait_use_lines:
            return info.trait_use_lines[-1] + 1
        
        if info.first_property_line is not None:
            return info.first_property_line
        
        # After class declaration (find the opening brace)
        return info.class_line + 1
    
    def has_use_statement(self, info: PhpClassInfo, fqcn: str) -> bool:
        """Check if a use statement already exists."""
        # Normalize FQCN (remove leading backslash)
        normalized = fqcn.lstrip("\\")
        
        for existing in info.use_statements:
            if existing.lstrip("\\") == normalized:
                return True
        
        return False
```

### Step 2: Update DIRefactoringContext

Update `drupalls/lsp/capabilities/di_refactoring/strategies/base.py`:

```python
"""
DI refactoring strategy base class.

File: drupalls/lsp/capabilities/di_refactoring/strategies/base.py
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from lsprotocol.types import TextEdit, Range, Position

if TYPE_CHECKING:
    from drupalls.lsp.capabilities.di_refactoring.php_class_analyzer import (
        PhpClassInfo,
    )


@dataclass
class DIRefactoringContext:
    """Context for DI refactoring."""

    file_uri: str
    file_content: str
    class_line: int
    drupal_type: str
    services_to_inject: list[str] = field(default_factory=list)
    
    # Analyzed class info (set by strategy)
    class_info: PhpClassInfo | None = None


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
    
    def _replace_lines(
        self, 
        start_line: int, 
        end_line: int, 
        new_text: str,
        lines: list[str]
    ) -> TextEdit:
        """Create a replace edit for a range of lines."""
        end_char = len(lines[end_line]) if end_line < len(lines) else 0
        return self._create_text_edit(
            start_line, 0, end_line, end_char, new_text
        )
```

### Step 3: Update ControllerDIStrategy

Rewrite `drupalls/lsp/capabilities/di_refactoring/strategies/controller_strategy.py`:

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
    ServiceInterfaceInfo,
)
from drupalls.lsp.capabilities.di_refactoring.php_class_analyzer import (
    PhpClassAnalyzer,
    PhpClassInfo,
)


class ControllerDIStrategy(DIStrategy):
    """DI strategy for Controllers and Forms using ContainerInjectionInterface."""

    def __init__(self) -> None:
        self.analyzer = PhpClassAnalyzer()

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
        lines = context.file_content.split("\n")
        
        # Analyze existing class structure
        class_info = self.analyzer.analyze(context.file_content)
        context.class_info = class_info

        # Collect service info for new services only
        new_services: list[tuple[str, ServiceInterfaceInfo | None]] = []
        for service_id in context.services_to_inject:
            # Skip if already injected in constructor
            if class_info.constructor:
                existing_gets = class_info.create_method.container_gets if class_info.create_method else []
                if service_id in existing_gets:
                    continue
            
            info = get_service_interface(service_id)
            new_services.append((service_id, info))
        
        if not new_services:
            return edits

        # 1. Generate use statement edits (only for new ones)
        use_edits = self._generate_use_statement_edits(
            class_info, new_services, lines
        )
        edits.extend(use_edits)

        # 2. Generate property edits (with docstrings)
        property_edits = self._generate_property_edits(
            class_info, new_services
        )
        edits.extend(property_edits)

        # 3. Generate constructor edit (merge or create)
        constructor_edit = self._generate_constructor_edit(
            class_info, new_services, lines
        )
        if constructor_edit:
            edits.append(constructor_edit)

        # 4. Generate create() edit (merge or create)
        create_edit = self._generate_create_edit(
            class_info, new_services, lines
        )
        if create_edit:
            edits.append(create_edit)

        return edits

    def _generate_use_statement_edits(
        self,
        class_info: PhpClassInfo,
        new_services: list[tuple[str, ServiceInterfaceInfo | None]],
        lines: list[str],
    ) -> list[RefactoringEdit]:
        """Generate use statement edits, avoiding duplicates."""
        edits: list[RefactoringEdit] = []
        new_use_statements: list[str] = []
        
        for service_id, info in new_services:
            if info is None:
                continue
            
            # Extract FQCN from use statement
            fqcn = info.interface_fqcn
            
            # Check if already exists
            if not self.analyzer.has_use_statement(class_info, fqcn):
                new_use_statements.append(info.use_statement)
        
        if new_use_statements:
            # Insert before class declaration
            insert_line = class_info.use_section_end
            if insert_line == 0:
                insert_line = class_info.class_line - 1
            
            text = "\n".join(new_use_statements) + "\n"
            edits.append(
                RefactoringEdit(
                    description="Add use statements",
                    text_edit=self._insert_at(insert_line, 0, text),
                )
            )
        
        return edits

    def _generate_property_edits(
        self,
        class_info: PhpClassInfo,
        new_services: list[tuple[str, ServiceInterfaceInfo | None]],
    ) -> list[RefactoringEdit]:
        """Generate property declarations with docstrings."""
        edits: list[RefactoringEdit] = []
        
        insert_line = self.analyzer.get_property_insert_line(class_info)
        
        property_text = "\n"
        for service_id, info in new_services:
            if info:
                prop_name = info.property_name
                interface_short = info.interface_short
                interface_fqcn = info.interface_fqcn
            else:
                prop_name = get_property_name(service_id)
                interface_short = ""
                interface_fqcn = "mixed"
            
            # Skip if property already exists
            if prop_name in class_info.properties:
                continue
            
            # Generate docstring
            service_label = service_id.replace(".", " ").replace("_", " ")
            property_text += f"""  /**
   * The {service_label} service.
   *
   * @var \\{interface_fqcn}
   */
  protected {interface_short + ' ' if interface_short else ''}${prop_name};

"""
        
        if property_text.strip():
            edits.append(
                RefactoringEdit(
                    description="Add properties with docstrings",
                    text_edit=self._insert_at(insert_line, 0, property_text),
                )
            )
        
        return edits

    def _generate_constructor_edit(
        self,
        class_info: PhpClassInfo,
        new_services: list[tuple[str, ServiceInterfaceInfo | None]],
        lines: list[str],
    ) -> RefactoringEdit | None:
        """Generate constructor edit - merge with existing or create new."""
        if class_info.constructor:
            return self._merge_constructor(
                class_info, new_services, lines
            )
        else:
            return self._create_new_constructor(
                class_info, new_services
            )

    def _merge_constructor(
        self,
        class_info: PhpClassInfo,
        new_services: list[tuple[str, ServiceInterfaceInfo | None]],
        lines: list[str],
    ) -> RefactoringEdit | None:
        """Merge new parameters into existing constructor."""
        ctor = class_info.constructor
        if ctor is None:
            return None
        
        # Build existing parameters string
        existing_params: list[str] = []
        for param_name, type_hint in ctor.params:
            if type_hint:
                existing_params.append(f"    {type_hint} ${param_name}")
            else:
                existing_params.append(f"    ${param_name}")
        
        # Add new parameters
        new_params: list[str] = []
        new_assignments: list[str] = []
        for service_id, info in new_services:
            if info:
                prop_name = info.property_name
                type_hint = info.interface_short
            else:
                prop_name = get_property_name(service_id)
                type_hint = ""
            
            if type_hint:
                new_params.append(f"    {type_hint} ${prop_name}")
            else:
                new_params.append(f"    ${prop_name}")
            new_assignments.append(f"    $this->{prop_name} = ${prop_name};")
        
        all_params = existing_params + new_params
        
        # Extract existing body (without closing brace)
        existing_body = "\n".join(ctor.body_lines).rstrip()
        if existing_body and not existing_body.endswith("\n"):
            existing_body += "\n"
        
        # Build merged constructor
        merged = (
            "  public function __construct(\n"
            + ",\n".join(all_params) + "\n"
            + "  ) {\n"
            + existing_body
            + "\n".join(new_assignments) + "\n"
            + "  }\n"
        )
        
        # Determine range to replace (including docblock if exists)
        start_line = ctor.docblock_start if ctor.docblock_start else ctor.start_line
        end_line = ctor.end_line
        
        # Get existing docblock
        docblock = ""
        if ctor.docblock_start is not None and ctor.docblock_end is not None:
            docblock = "\n".join(
                lines[ctor.docblock_start:ctor.docblock_end + 1]
            ) + "\n"
        
        return RefactoringEdit(
            description="Merge constructor with new services",
            text_edit=self._replace_lines(
                start_line, end_line, docblock + merged, lines
            ),
        )

    def _create_new_constructor(
        self,
        class_info: PhpClassInfo,
        new_services: list[tuple[str, ServiceInterfaceInfo | None]],
    ) -> RefactoringEdit | None:
        """Create new constructor when none exists."""
        params: list[str] = []
        assignments: list[str] = []
        
        for service_id, info in new_services:
            if info:
                prop_name = info.property_name
                type_hint = info.interface_short
            else:
                prop_name = get_property_name(service_id)
                type_hint = ""
            
            if type_hint:
                params.append(f"    {type_hint} ${prop_name}")
            else:
                params.append(f"    ${prop_name}")
            assignments.append(f"    $this->{prop_name} = ${prop_name};")
        
        constructor = (
            "\n  /**\n"
            "   * Constructs the object.\n"
            "   */\n"
            "  public function __construct(\n"
            + ",\n".join(params) + "\n"
            + "  ) {\n"
            + "\n".join(assignments) + "\n"
            + "  }\n\n"
        )
        
        # Insert after properties
        insert_line = class_info.first_property_line or class_info.class_line + 2
        if class_info.properties:
            # Find last property
            last_prop_line = max(p.line for p in class_info.properties.values())
            insert_line = last_prop_line + 2
        
        return RefactoringEdit(
            description="Add constructor",
            text_edit=self._insert_at(insert_line, 0, constructor),
        )

    def _generate_create_edit(
        self,
        class_info: PhpClassInfo,
        new_services: list[tuple[str, ServiceInterfaceInfo | None]],
        lines: list[str],
    ) -> RefactoringEdit | None:
        """Generate create() edit - merge or create."""
        if class_info.create_method:
            return self._merge_create_method(
                class_info, new_services, lines
            )
        else:
            return self._create_new_create_method(
                class_info, new_services
            )

    def _merge_create_method(
        self,
        class_info: PhpClassInfo,
        new_services: list[tuple[str, ServiceInterfaceInfo | None]],
        lines: list[str],
    ) -> RefactoringEdit | None:
        """Merge new container gets into existing create()."""
        create = class_info.create_method
        if create is None:
            return None
        
        # Get existing container gets
        existing_gets = [
            f"      $container->get('{sid}')"
            for sid in create.container_gets
        ]
        
        # Add new container gets
        new_gets = [
            f"      $container->get('{service_id}')"
            for service_id, _ in new_services
        ]
        
        all_gets = existing_gets + new_gets
        
        merged = (
            "  /**\n"
            "   * {@inheritdoc}\n"
            "   */\n"
            "  public static function create(ContainerInterface $container) {\n"
            "    return new static(\n"
            + ",\n".join(all_gets) + "\n"
            + "    );\n"
            + "  }\n"
        )
        
        start_line = create.docblock_start if create.docblock_start else create.start_line
        end_line = create.end_line
        
        return RefactoringEdit(
            description="Merge create() with new container gets",
            text_edit=self._replace_lines(start_line, end_line, merged, lines),
        )

    def _create_new_create_method(
        self,
        class_info: PhpClassInfo,
        new_services: list[tuple[str, ServiceInterfaceInfo | None]],
    ) -> RefactoringEdit | None:
        """Create new create() method."""
        gets = [
            f"      $container->get('{service_id}')"
            for service_id, _ in new_services
        ]
        
        create = (
            "\n  /**\n"
            "   * {@inheritdoc}\n"
            "   */\n"
            "  public static function create(ContainerInterface $container) {\n"
            "    return new static(\n"
            + ",\n".join(gets) + "\n"
            + "    );\n"
            + "  }\n\n"
        )
        
        # Insert after constructor if exists
        if class_info.constructor:
            insert_line = class_info.constructor.end_line + 1
        else:
            insert_line = class_info.class_line + 2
        
        return RefactoringEdit(
            description="Add create() method",
            text_edit=self._insert_at(insert_line, 0, create),
        )
```

### Step 4: Add Missing Service Interfaces

Add to `drupalls/lsp/capabilities/di_refactoring/service_interfaces.py`:

```python
    "renderer": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Core\\Render\\RendererInterface",
        interface_short="RendererInterface",
        property_name="renderer",
        use_statement="use Drupal\\Core\\Render\\RendererInterface;",
    ),
    "entity.repository": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Core\\Entity\\EntityRepositoryInterface",
        interface_short="EntityRepositoryInterface",
        property_name="entityRepository",
        use_statement="use Drupal\\Core\\Entity\\EntityRepositoryInterface;",
    ),
    "date.formatter": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Core\\Datetime\\DateFormatterInterface",
        interface_short="DateFormatterInterface",
        property_name="dateFormatter",
        use_statement="use Drupal\\Core\\Datetime\\DateFormatterInterface;",
    ),
    "entity.manager": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Core\\Entity\\EntityManagerInterface",
        interface_short="EntityManagerInterface",
        property_name="entityManager",
        use_statement="use Drupal\\Core\\Entity\\EntityManagerInterface;",
    ),
    "file_system": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\Core\\File\\FileSystemInterface",
        interface_short="FileSystemInterface",
        property_name="fileSystem",
        use_statement="use Drupal\\Core\\File\\FileSystemInterface;",
    ),
    "path.alias_manager": ServiceInterfaceInfo(
        interface_fqcn="Drupal\\path_alias\\AliasManagerInterface",
        interface_short="AliasManagerInterface",
        property_name="aliasManager",
        use_statement="use Drupal\\path_alias\\AliasManagerInterface;",
    ),
```

### Step 5: Update __init__.py

Update `drupalls/lsp/capabilities/di_refactoring/__init__.py`:

```python
"""DI refactoring module."""
from drupalls.lsp.capabilities.di_refactoring.static_call_detector import (
    StaticCallDetector,
    StaticServiceCall,
)
from drupalls.lsp.capabilities.di_refactoring.service_interfaces import (
    ServiceInterfaceInfo,
    get_service_interface,
    get_property_name,
)
from drupalls.lsp.capabilities.di_refactoring.php_class_analyzer import (
    PhpClassAnalyzer,
    PhpClassInfo,
    ConstructorInfo,
    CreateMethodInfo,
    PropertyInfo,
)
from drupalls.lsp.capabilities.di_refactoring.strategy_factory import (
    DIStrategyFactory,
)

__all__ = [
    "StaticCallDetector",
    "StaticServiceCall",
    "ServiceInterfaceInfo",
    "get_service_interface",
    "get_property_name",
    "PhpClassAnalyzer",
    "PhpClassInfo",
    "ConstructorInfo",
    "CreateMethodInfo",
    "PropertyInfo",
    "DIStrategyFactory",
]
```

## Edge Cases

### 1. No Existing Constructor

When the class has no `__construct()`:
- Create new constructor with all new service parameters
- Insert after properties section

### 2. No Existing create()

When the class has no `create()` method:
- Create new create() method with all container gets
- Insert after constructor

### 3. Services Already Injected

When a service is already in the constructor:
- Skip adding duplicate parameter
- Skip adding duplicate property
- Skip adding duplicate container get

### 4. Class with Trait Uses

When class has `use TraitName;` statements:
- Insert new properties after trait use statements
- Before existing properties

### 5. Properties Without Docstrings

When adding new properties:
- Always generate full docstring with `@var` annotation
- Use service interface FQCN in `@var`

### 6. Multiple Static Calls for Same Service

When `\Drupal::service('renderer')` appears multiple times:
- Only add one property, one constructor param, one container get
- Replace all occurrences with `$this->renderer`

## Testing

### Unit Tests for PhpClassAnalyzer

```python
# tests/lsp/capabilities/di_refactoring/test_php_class_analyzer.py

import pytest
from drupalls.lsp.capabilities.di_refactoring.php_class_analyzer import (
    PhpClassAnalyzer,
)


@pytest.fixture
def analyzer():
    return PhpClassAnalyzer()


def test_parse_use_statements(analyzer):
    content = '''<?php
namespace Test;

use Drupal\\Core\\Controller\\ControllerBase;
use Symfony\\Component\\DependencyInjection\\ContainerInterface;

class MyController extends ControllerBase {
}
'''
    info = analyzer.analyze(content)
    
    assert len(info.use_statements) == 2
    assert "Drupal\\Core\\Controller\\ControllerBase" in info.use_statements
    assert "Symfony\\Component\\DependencyInjection\\ContainerInterface" in info.use_statements


def test_parse_existing_constructor(analyzer):
    content = '''<?php
class MyController {
  public function __construct(
    DateFormatter $dateFormatter,
    EntityTypeManager $entityTypeManager
  ) {
    $this->dateFormatter = $dateFormatter;
    $this->entityTypeManager = $entityTypeManager;
  }
}
'''
    info = analyzer.analyze(content)
    
    assert info.constructor is not None
    assert len(info.constructor.params) == 2
    assert info.constructor.params[0] == ("dateFormatter", "DateFormatter")
    assert info.constructor.params[1] == ("entityTypeManager", "EntityTypeManager")


def test_parse_existing_create(analyzer):
    content = '''<?php
class MyController {
  public static function create(ContainerInterface $container) {
    return new static(
      $container->get('date.formatter'),
      $container->get('entity_type.manager')
    );
  }
}
'''
    info = analyzer.analyze(content)
    
    assert info.create_method is not None
    assert len(info.create_method.container_gets) == 2
    assert "date.formatter" in info.create_method.container_gets
    assert "entity_type.manager" in info.create_method.container_gets


def test_detect_existing_use_statement(analyzer):
    content = '''<?php
use Symfony\\Component\\DependencyInjection\\ContainerInterface;

class MyController {
}
'''
    info = analyzer.analyze(content)
    
    assert analyzer.has_use_statement(
        info, "Symfony\\Component\\DependencyInjection\\ContainerInterface"
    )
    assert not analyzer.has_use_statement(
        info, "Drupal\\Core\\Render\\RendererInterface"
    )


def test_property_insert_line_with_traits(analyzer):
    content = '''<?php
class MyController {
  use SomeTrait;
  use AnotherTrait;
  
  protected $existingProp;
}
'''
    info = analyzer.analyze(content)
    
    # Should insert after traits, before first property
    insert_line = analyzer.get_property_insert_line(info)
    assert insert_line > max(info.trait_use_lines)
```

### Integration Test

```python
# tests/lsp/capabilities/di_refactoring/test_controller_strategy_merge.py

import pytest
from drupalls.lsp.capabilities.di_refactoring.strategies.controller_strategy import (
    ControllerDIStrategy,
)
from drupalls.lsp.capabilities.di_refactoring.strategies.base import (
    DIRefactoringContext,
)


BEFORE_CONTENT = '''<?php
namespace Test;

use Drupal\\Core\\Controller\\ControllerBase;
use Symfony\\Component\\DependencyInjection\\ContainerInterface;

class MyController extends ControllerBase {
  protected $existingService;
  
  public function __construct($existingService) {
    $this->existingService = $existingService;
  }
  
  public static function create(ContainerInterface $container) {
    return new static(
      $container->get('existing.service')
    );
  }
}
'''


def test_merge_with_existing_constructor():
    strategy = ControllerDIStrategy()
    context = DIRefactoringContext(
        file_uri="file:///test.php",
        file_content=BEFORE_CONTENT,
        class_line=7,
        drupal_type="controller",
        services_to_inject=["renderer"],
    )
    
    edits = strategy.generate_edits(context)
    
    # Should have edits for: use statement, property, constructor, create
    assert len(edits) >= 3
    
    # Check that constructor edit merges (not replaces)
    constructor_edit = next(
        (e for e in edits if "constructor" in e.description.lower()), None
    )
    assert constructor_edit is not None
    
    # The edit should contain both existing and new parameters
    new_text = constructor_edit.text_edit.new_text
    assert "$existingService" in new_text
    assert "RendererInterface" in new_text or "$renderer" in new_text
```

## Performance Considerations

### Caching

The `PhpClassAnalyzer` parses the file once per code action request. For large files, consider:

```python
# Cache analysis results by file content hash
import hashlib

class CachingPhpClassAnalyzer(PhpClassAnalyzer):
    def __init__(self):
        super().__init__()
        self._cache: dict[str, PhpClassInfo] = {}
    
    def analyze(self, content: str) -> PhpClassInfo:
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        if content_hash in self._cache:
            return self._cache[content_hash]
        
        info = super().analyze(content)
        self._cache[content_hash] = info
        return info
    
    def clear_cache(self) -> None:
        self._cache.clear()
```

### Edit Ordering

Edits must be applied in reverse order (bottom to top) to maintain correct line numbers:

```python
# In di_code_action.py _resolve_convert_all()

# Sort edits by line number (descending)
all_text_edits.sort(
    key=lambda e: (e.range.start.line, e.range.start.character),
    reverse=True,
)
```

## References

- **IMPLEMENTATION-017-DEPENDENCY_INJECTION_CODE_ACTION.md**: Original DI code action implementation
- **LSP TextEdit Specification**: https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textEdit
- **Drupal Dependency Injection**: https://www.drupal.org/docs/drupal-apis/services-and-dependency-injection

## File Structure After Implementation

```
drupalls/lsp/capabilities/di_refactoring/
├── __init__.py                    # Updated exports
├── static_call_detector.py        # Unchanged
├── service_interfaces.py          # Added renderer, entity.repository
├── php_class_analyzer.py          # NEW - Class structure analysis
├── strategy_factory.py            # Unchanged
└── strategies/
    ├── __init__.py
    ├── base.py                    # Updated DIRefactoringContext
    ├── controller_strategy.py     # MAJOR REWRITE - Merge logic
    └── plugin_strategy.py         # Similar updates needed
```
