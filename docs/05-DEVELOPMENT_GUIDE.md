# Drupal Language Server Development Guide

## Table of Contents

1. [Overview](#overview)
2. [What is Language Server Protocol (LSP)?](#what-is-language-server-protocol-lsp)
3. [Project Structure](#project-structure)
4. [Step-by-Step Implementation](#step-by-step-implementation)
5. [Key pygls v2 APIs](#key-pygls-v2-apis)
6. **[Complete LSP Feature Reference](#complete-lsp-feature-reference)** ⭐ NEW
   - Text Synchronization Features
   - Code Intelligence Features
   - Code Modification Features
   - Diagnostics Features
   - Document Symbol Features
   - Linking and Navigation Features
   - Visual Features
   - Advanced Features
7. **[Feature Priority for Drupal](#feature-priority-for-drupal)** ⭐ NEW
8. [Running the Server](#running-the-server)
9. [Testing](#testing)
10. [Next Steps for Drupal-Specific Features](#next-steps-for-drupal-specific-features)
11. **[Practical Drupal Implementation Examples](#practical-drupal-implementation-examples)** ⭐ NEW
    - Example 1: Detect and Warn About Deprecated Functions
    - Example 2: Autocomplete Drupal Services
    - Example 3: Go to Service Definition
    - Example 4: Show Hook Signature on Hover
    - Example 5: Code Actions for Quick Fixes
    - Example 6: Document Symbols (Outline View)
12. [Debugging Tips](#debugging-tips)
13. [Resources](#resources)
14. **[Integrating with Phpactor Language Server](#integrating-with-phpactor-language-server)** ⭐ NEW
    - Strategy 1: Run Both Servers (Recommended)
    - Strategy 2: Create a Phpactor Extension
    - Strategy 3: Proxy/Wrapper Server
    - Implementation Examples for VS Code, Neovim, Sublime
    - Handling Feature Overlap
    - Smart Delegation Pattern
    - Testing Both Servers Together

---

## Overview

This guide explains how to build a Language Server Protocol (LSP) implementation for Drupal using pygls v2.

## What is Language Server Protocol (LSP)?

LSP is a standard protocol that enables editors (VS Code, Neovim, Vim, etc.) to provide rich language features. The protocol defines 40+ features that language servers can implement. The most common ones are:

- **Autocomplete** - Suggestions as you type
- **Hover Information** - Documentation on hover
- **Go to Definition** - Jump to where something is defined
- **Find References** - Find all uses of a symbol
- **Diagnostics** - Errors and warnings
- **Code Actions** - Quick fixes and refactorings
- **Formatting** - Automatic code formatting
- **Rename** - Rename symbols across files
- **And many more...**

### How LSP Works

```
┌─────────────┐                    ┌──────────────────┐
│   Editor    │  ←── JSON-RPC ──→  │ Language Server  │
│  (Client)   │                    │    (Python)      │
└─────────────┘                    └──────────────────┘
      ↑                                      ↑
      │                                      │
   User types                          Analyzes code
   Opens files                         Returns results
```

**Communication Flow:**
1. Editor starts the language server process
2. They communicate via JSON-RPC over stdin/stdout
3. Editor sends requests/notifications (file opened, text changed, completion requested)
4. Server responds with results (completion items, hover info, diagnostics)

## Project Structure

```
drupalls/
├── __init__.py
├── main.py              # Entry point (python -m drupalls)
├── lsp/
│   ├── __init__.py
│   ├── server.py            # Server creation and setup
│   ├── capabilities.py      # LSP capability definitions
│   └── features/            # Feature implementations
│       ├── __init__.py
│       ├── text_sync.py     # Document synchronization
│       ├── completion.py    # Autocomplete
│       └── hover.py         # Hover information
└── agents/                  # Future: code analysis agents
```

## Step-by-Step Implementation

### Step 1: Understanding pygls v2 Basics

**Key Concepts:**

1. **LanguageServer**: The main server class that handles JSON-RPC communication
   ```python
   from pygls.lsp.server import LanguageServer
   server = LanguageServer("name", "version")
   ```

2. **Features**: Functions decorated with `@server.feature()` that handle LSP requests
   ```python
   @server.feature(TEXT_DOCUMENT_COMPLETION)
   def completions(ls: LanguageServer, params: CompletionParams):
       return CompletionList(items=[...])
   ```

3. **Notifications vs Requests**:
   - **Notifications**: Client sends but doesn't expect a response (didOpen, didChange)
   - **Requests**: Client expects a response (completion, hover, definition)

### Step 2: Create Basic Server

The server needs three things:
1. Creation function (`create_server()`)
2. Feature registration (hooks for LSP methods)
3. Entry point to start IO communication

See `drupalls/lsp/server.py` and `drupalls/main.py`

### Step 3: Implement Text Synchronization

Text sync keeps the server aware of what files are open and their contents.

**Essential Events:**
- `textDocument/didOpen` - File opened in editor
- `textDocument/didChange` - File content changed
- `textDocument/didSave` - File saved
- `textDocument/didClose` - File closed

The server automatically stores document content in `server.workspace.text_documents`.

**Implementation:** See `drupalls/lsp/features/text_sync.py`

### Step 4: Implement Completion (Autocomplete)

Completion provides suggestions as the user types.

**Process:**
1. User types (e.g., "hook_")
2. Editor sends completion request with cursor position
3. Server analyzes context and returns completion items
4. Editor shows suggestions to user

**For Drupal:**
- Detect context (in hook? in service call?)
- Provide relevant completions (hooks, services, config keys)

**Implementation:** See `drupalls/lsp/features/completion.py`

### Step 5: Implement Hover

Hover shows information when user hovers over code.

**Process:**
1. User hovers over a word
2. Editor sends hover request with position
3. Server identifies the word and looks up documentation
4. Server returns markdown-formatted documentation
5. Editor displays it in a popup

**For Drupal:**
- Identify Drupal hooks, functions, services
- Return API documentation, signatures, examples

**Implementation:** See `drupalls/lsp/features/hover.py`

## Key pygls v2 APIs

### LanguageServer Methods

```python
# Access open documents
document = server.workspace.get_text_document(uri)

# Get document content
content = document.source
lines = document.lines

# Send messages to client (for debugging)
server.show_message_log("Debug message")
server.show_message("User-visible message")

# Publish diagnostics (errors/warnings)
server.publish_diagnostics(uri, diagnostics)
```

### Important Types (from lsprotocol.types)

```python
# Requests
TEXT_DOCUMENT_COMPLETION
TEXT_DOCUMENT_HOVER
TEXT_DOCUMENT_DEFINITION
TEXT_DOCUMENT_REFERENCES

# Notifications
TEXT_DOCUMENT_DID_OPEN
TEXT_DOCUMENT_DID_CHANGE
TEXT_DOCUMENT_DID_SAVE
TEXT_DOCUMENT_DID_CLOSE

# Data structures
CompletionItem(label="hook_form_alter", kind=CompletionItemKind.Function)
Hover(contents=MarkupContent(kind=MarkupKind.Markdown, value="# Documentation"))
Diagnostic(range=Range(...), severity=DiagnosticSeverity.Error, message="Error")
```

## Complete LSP Feature Reference

LSP defines 40+ features you can implement. Here's a comprehensive guide:

### 📝 Text Synchronization Features

These track document state between editor and server:

| Feature | Type | Purpose | Drupal Use Case |
|---------|------|---------|-----------------|
| `TEXT_DOCUMENT_DID_OPEN` | Notification | File opened in editor | Start tracking .php/.module files |
| `TEXT_DOCUMENT_DID_CHANGE` | Notification | File content changed | Update parsing, trigger diagnostics |
| `TEXT_DOCUMENT_DID_SAVE` | Notification | File saved | Run full analysis, update caches |
| `TEXT_DOCUMENT_DID_CLOSE` | Notification | File closed | Clean up resources |
| `TEXT_DOCUMENT_WILL_SAVE` | Notification | About to save | Pre-save validation |
| `TEXT_DOCUMENT_WILL_SAVE_WAIT_UNTIL` | Request | Before save, can edit | Auto-format before save |

**Implementation Example:**
```python
@server.feature(TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: LanguageServer, params: DidOpenTextDocumentParams):
    doc = ls.workspace.get_text_document(params.text_document.uri)
    # Parse Drupal hooks, validate syntax, etc.
```

### 🔍 Code Intelligence Features

Core features for understanding and navigating code:

| Feature | Type | Purpose | Drupal Use Case |
|---------|------|---------|-----------------|
| `TEXT_DOCUMENT_COMPLETION` | Request | Autocomplete suggestions | Hook names, service IDs, config keys |
| `TEXT_DOCUMENT_HOVER` | Request | Show info on hover | Drupal API docs, hook signatures |
| `TEXT_DOCUMENT_SIGNATURE_HELP` | Request | Parameter hints while typing | Show hook parameters as you type |
| `TEXT_DOCUMENT_DEFINITION` | Request | Go to definition | Jump to service class, hook implementation |
| `TEXT_DOCUMENT_DECLARATION` | Request | Go to declaration | Jump to interface/trait declaration |
| `TEXT_DOCUMENT_TYPE_DEFINITION` | Request | Go to type definition | Jump to entity type class |
| `TEXT_DOCUMENT_IMPLEMENTATION` | Request | Find implementations | Find all hook_form_alter implementations |
| `TEXT_DOCUMENT_REFERENCES` | Request | Find all references | Where is this service used? |

**Completion Example:**
```python
@server.feature(TEXT_DOCUMENT_COMPLETION)
def completions(ls: LanguageServer, params: CompletionParams) -> CompletionList:
    items = [
        CompletionItem(
            label="hook_form_alter",
            kind=CompletionItemKind.Function,
            detail="Alter forms before rendering",
            insert_text="hook_form_alter(&$form, $form_state, $form_id) {\n  $0\n}",
            insert_text_format=InsertTextFormat.Snippet,
        )
    ]
    return CompletionList(is_incomplete=False, items=items)
```

**Go to Definition Example:**
```python
@server.feature(TEXT_DOCUMENT_DEFINITION)
def definition(ls: LanguageServer, params: DefinitionParams) -> Location:
    # Parse service ID at cursor position
    # Return location of service class definition
    return Location(
        uri="file:///path/to/Service.php",
        range=Range(start=Position(line=10, character=0), end=Position(line=10, character=20))
    )
```

### 🎨 Code Modification Features

Features that modify code:

| Feature | Type | Purpose | Drupal Use Case |
|---------|------|---------|-----------------|
| `TEXT_DOCUMENT_FORMATTING` | Request | Format entire document | Format PHP according to Drupal coding standards |
| `TEXT_DOCUMENT_RANGE_FORMATTING` | Request | Format selection | Format selected code block |
| `TEXT_DOCUMENT_ON_TYPE_FORMATTING` | Request | Format while typing | Auto-indent after `{`, format after `;` |
| `TEXT_DOCUMENT_RENAME` | Request | Rename symbol | Rename service across all files |
| `TEXT_DOCUMENT_PREPARE_RENAME` | Request | Validate rename | Check if symbol can be renamed |
| `TEXT_DOCUMENT_CODE_ACTION` | Request | Quick fixes/refactorings | "Replace deprecated function", "Add @file docblock" |

**Code Action Example:**
```python
@server.feature(TEXT_DOCUMENT_CODE_ACTION)
def code_actions(ls: LanguageServer, params: CodeActionParams) -> List[CodeAction]:
    actions = []
    
    # If deprecated function detected, offer replacement
    if is_deprecated_function(params.range):
        actions.append(
            CodeAction(
                title="Replace with modern API",
                kind=CodeActionKind.QuickFix,
                edit=WorkspaceEdit(changes={params.text_document.uri: [TextEdit(...)]}),
            )
        )
    
    return actions
```

**Formatting Example:**
```python
@server.feature(TEXT_DOCUMENT_FORMATTING)
def formatting(ls: LanguageServer, params: DocumentFormattingParams) -> List[TextEdit]:
    doc = ls.workspace.get_text_document(params.text_document.uri)
    formatted = apply_drupal_coding_standards(doc.source)
    
    # Return edit that replaces entire document
    return [
        TextEdit(
            range=Range(
                start=Position(line=0, character=0),
                end=Position(line=len(doc.lines), character=0)
            ),
            new_text=formatted
        )
    ]
```

### 🔴 Diagnostics Features

Report errors, warnings, and information:

| Feature | Type | Purpose | Drupal Use Case |
|---------|------|---------|-----------------|
| `TEXT_DOCUMENT_PUBLISH_DIAGNOSTICS` | Notification (server→client) | Send errors/warnings | Deprecated API usage, missing dependencies |
| `TEXT_DOCUMENT_DIAGNOSTIC` | Request | Pull diagnostics | Get diagnostics on demand |

**Diagnostics Example:**
```python
from lsprotocol.types import Diagnostic, DiagnosticSeverity

def validate_drupal_code(ls: LanguageServer, uri: str):
    doc = ls.workspace.get_text_document(uri)
    diagnostics = []
    
    # Check for deprecated functions
    for line_num, line in enumerate(doc.lines):
        if "drupal_set_message" in line:
            diagnostics.append(
                Diagnostic(
                    range=Range(
                        start=Position(line=line_num, character=0),
                        end=Position(line=line_num, character=len(line))
                    ),
                    severity=DiagnosticSeverity.Warning,
                    message="drupal_set_message() is deprecated. Use Messenger service instead.",
                    source="drupalls",
                )
            )
    
    ls.publish_diagnostics(uri, diagnostics)

# Call this from did_change or did_save handler
@server.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: LanguageServer, params: DidChangeTextDocumentParams):
    validate_drupal_code(ls, params.text_document.uri)
```

### 📊 Document Symbol Features

Show document structure and symbols:

| Feature | Type | Purpose | Drupal Use Case |
|---------|------|---------|-----------------|
| `TEXT_DOCUMENT_DOCUMENT_SYMBOL` | Request | Outline/breadcrumb | Show functions, hooks, classes in file |
| `TEXT_DOCUMENT_DOCUMENT_HIGHLIGHT` | Request | Highlight same symbol | Highlight all uses of $variable |
| `TEXT_DOCUMENT_SELECTION_RANGE` | Request | Smart selection | Select function, then entire hook |
| `TEXT_DOCUMENT_FOLDING_RANGE` | Request | Code folding regions | Fold functions, classes, arrays |

**Document Symbol Example:**
```python
@server.feature(TEXT_DOCUMENT_DOCUMENT_SYMBOL)
def document_symbols(ls: LanguageServer, params: DocumentSymbolParams) -> List[DocumentSymbol]:
    doc = ls.workspace.get_text_document(params.text_document.uri)
    symbols = []
    
    # Parse and return all functions/hooks
    for func_name, start_line, end_line in parse_functions(doc.source):
        symbols.append(
            DocumentSymbol(
                name=func_name,
                kind=SymbolKind.Function,
                range=Range(
                    start=Position(line=start_line, character=0),
                    end=Position(line=end_line, character=0)
                ),
                selection_range=Range(...)  # The name itself
            )
        )
    
    return symbols
```

### 🔗 Linking and Navigation Features

| Feature | Type | Purpose | Drupal Use Case |
|---------|------|---------|-----------------|
| `TEXT_DOCUMENT_DOCUMENT_LINK` | Request | Clickable links in code | Make URLs in comments clickable |
| `TEXT_DOCUMENT_LINKED_EDITING_RANGE` | Request | Edit multiple locations | Edit opening and closing PHP tags together |
| `CALL_HIERARCHY` | Request | Show call graph | Show what calls/is called by this function |

### 🎨 Visual Features

| Feature | Type | Purpose | Drupal Use Case |
|---------|------|---------|-----------------|
| `TEXT_DOCUMENT_CODE_LENS` | Request | Inline annotations | Show "3 implementations" above hook |
| `TEXT_DOCUMENT_INLAY_HINT` | Request | Inline hints | Show parameter names in function calls |
| `TEXT_DOCUMENT_DOCUMENT_COLOR` | Request | Color picker | Show color preview for CSS in theme |
| `TEXT_DOCUMENT_COLOR_PRESENTATION` | Request | Color formats | Convert hex to rgb |
| `TEXT_DOCUMENT_SEMANTIC_TOKENS` | Request | Semantic highlighting | Color-code based on meaning, not syntax |

**Code Lens Example:**
```python
@server.feature(TEXT_DOCUMENT_CODE_LENS)
def code_lens(ls: LanguageServer, params: CodeLensParams) -> List[CodeLens]:
    doc = ls.workspace.get_text_document(params.text_document.uri)
    lenses = []
    
    # Find hook definitions and count implementations
    if is_hook_definition(doc):
        impl_count = count_hook_implementations("hook_form_alter")
        lenses.append(
            CodeLens(
                range=Range(start=Position(line=10, character=0), end=Position(line=10, character=20)),
                command=Command(
                    title=f"{impl_count} implementations",
                    command="drupalls.showImplementations"
                )
            )
        )
    
    return lenses
```

**Inlay Hints Example:**
```python
@server.feature(TEXT_DOCUMENT_INLAY_HINT)
def inlay_hints(ls: LanguageServer, params: InlayHintParams) -> List[InlayHint]:
    # Show parameter names for function calls
    # \Drupal::service('entity_type.manager')
    #                   ^^^^^^^^ show: "service_id:"
    return [
        InlayHint(
            position=Position(line=5, character=17),
            label="service_id:",
            kind=InlayHintKind.Parameter,
        )
    ]
```

### 🧪 Advanced Features

| Feature | Type | Purpose | Drupal Use Case |
|---------|------|---------|-----------------|
| `TEXT_DOCUMENT_INLINE_COMPLETION` | Request | AI-style inline completion | Suggest entire function implementation |
| `TEXT_DOCUMENT_MONIKER` | Request | Cross-project symbols | Link Drupal core symbols to api.drupal.org |
| `TEXT_DOCUMENT_INLINE_VALUE` | Request | Debugger variable values | Show values during debugging |
| `TYPE_HIERARCHY` | Request | Type inheritance tree | Show entity class hierarchy |

## Feature Priority for Drupal

Here's a recommended implementation order for Drupal:

### ✅ Essential (Implement First)
1. **TEXT_DOCUMENT_DID_OPEN/CHANGE/SAVE** - Already implemented
2. **TEXT_DOCUMENT_COMPLETION** - Already implemented
3. **TEXT_DOCUMENT_HOVER** - Already implemented
4. **TEXT_DOCUMENT_PUBLISH_DIAGNOSTICS** - Validate Drupal code
5. **TEXT_DOCUMENT_DEFINITION** - Jump to service/plugin definitions

### 🎯 High Value (Implement Next)
6. **TEXT_DOCUMENT_REFERENCES** - Find hook implementations
7. **TEXT_DOCUMENT_DOCUMENT_SYMBOL** - Show file outline
8. **TEXT_DOCUMENT_CODE_ACTION** - Quick fixes for deprecations
9. **TEXT_DOCUMENT_SIGNATURE_HELP** - Show hook parameters
10. **TEXT_DOCUMENT_FORMATTING** - Drupal coding standards

### 💡 Nice to Have
11. **TEXT_DOCUMENT_CODE_LENS** - Show implementation counts
12. **TEXT_DOCUMENT_RENAME** - Rename services safely
13. **TEXT_DOCUMENT_IMPLEMENTATION** - Find all hook implementations
14. **TEXT_DOCUMENT_INLAY_HINT** - Show parameter names
15. **TEXT_DOCUMENT_FOLDING_RANGE** - Code folding

### 🚀 Advanced
16. **TEXT_DOCUMENT_SEMANTIC_TOKENS** - Better syntax highlighting
17. **CALL_HIERARCHY** - Function call graphs
18. **TEXT_DOCUMENT_INLINE_COMPLETION** - AI-assisted coding

## Running the Server

### Standalone (for testing)
```bash
poetry run python -m drupalls
```

### With an Editor

**VS Code** - Create `.vscode/settings.json`:
```json
{
  "drupalls.enabled": true,
  "drupalls.server.command": "/path/to/poetry",
  "drupalls.server.args": ["run", "python", "-m", "drupalls"]
}
```

**Neovim** - Using nvim-lspconfig:
```lua
require('lspconfig').drupalls.setup{
  cmd = { 'poetry', 'run', 'python', '-m', 'drupalls' },
  filetypes = { 'php' },
  root_dir = function(fname)
    return vim.fn.getcwd()
  end,
}
```

## Testing

```bash
# Run all tests
poetry run pytest

# Run specific test
poetry run pytest test/test_server_basic.py -v

# Test with coverage
poetry run pytest --cov=drupalls
```

## Next Steps for Drupal-Specific Features

### 1. Service Definition Go-To
- Parse `*.services.yml` files
- When user clicks on `\Drupal::service('entity_type.manager')`
- Jump to service definition in services.yml or the class itself

### 2. Hook Implementation Detection
- Scan module files for hook implementations
- Provide "implementations" lens/reference for hook definitions

### 3. Configuration Autocomplete
- Parse `config/schema/*.schema.yml`
- Autocomplete config keys in `\Drupal::config('...')`

### 4. Deprecation Warnings
- Maintain list of deprecated Drupal functions
- Show warnings when used
- Offer quick-fix to modern replacement

### 5. Template Variable Completion
- Parse `.module` files for `hook_theme()`
- Provide variable completions in `.html.twig` files

### 6. Annotation/Attribute Parsing
- Parse plugin annotations/attributes
- Provide validation and completion

## Practical Drupal Implementation Examples

Here are complete, working examples for common Drupal scenarios:

### Example 1: Detect and Warn About Deprecated Functions

```python
from lsprotocol.types import (
    TEXT_DOCUMENT_DID_CHANGE,
    Diagnostic,
    DiagnosticSeverity,
    Range,
    Position,
)

# Database of deprecated functions
DEPRECATED_FUNCTIONS = {
    "drupal_set_message": {
        "replacement": "\\Drupal::messenger()->addMessage()",
        "since": "8.5.0",
        "docs": "https://www.drupal.org/node/2774931",
    },
    "entity_load": {
        "replacement": "\\Drupal::entityTypeManager()->getStorage()->load()",
        "since": "8.0.0",
        "docs": "https://www.drupal.org/node/2266845",
    },
    "db_query": {
        "replacement": "\\Drupal::database()->query()",
        "since": "8.0.0",
        "docs": "https://www.drupal.org/node/2993033",
    },
}

@server.feature(TEXT_DOCUMENT_DID_CHANGE)
def check_deprecated(ls: LanguageServer, params: DidChangeTextDocumentParams):
    doc = ls.workspace.get_text_document(params.text_document.uri)
    diagnostics = []
    
    for line_num, line in enumerate(doc.lines):
        for func_name, info in DEPRECATED_FUNCTIONS.items():
            if func_name in line:
                # Find the position of the function name
                col = line.find(func_name)
                diagnostics.append(
                    Diagnostic(
                        range=Range(
                            start=Position(line=line_num, character=col),
                            end=Position(line=line_num, character=col + len(func_name))
                        ),
                        severity=DiagnosticSeverity.Warning,
                        message=f"{func_name}() is deprecated since Drupal {info['since']}. "
                               f"Use {info['replacement']} instead.",
                        source="drupalls",
                        code="deprecated",
                        code_description=CodeDescription(href=info['docs']),
                    )
                )
    
    ls.publish_diagnostics(params.text_document.uri, diagnostics)
```

### Example 2: Autocomplete Drupal Services

```python
from lsprotocol.types import CompletionItem, CompletionItemKind, CompletionList

# Load from services.yml or hardcode common ones
DRUPAL_SERVICES = {
    "entity_type.manager": "Manages entity type definitions",
    "entity_type.bundle.info": "Provides information about entity bundles",
    "entity_field.manager": "Manages entity field definitions",
    "database": "The database connection",
    "cache.default": "Default cache backend",
    "cache.render": "Render cache backend",
    "config.factory": "Configuration factory service",
    "current_user": "The current user",
    "current_route_match": "The current route match",
    "messenger": "Messenger service for user messages",
    "logger.factory": "Logger factory service",
    "module_handler": "Module handler service",
    "theme_handler": "Theme handler service",
    "state": "State API service",
    "keyvalue": "Key-value storage",
    "tempstore.private": "Private temporary storage",
    "account_switcher": "Account switcher service",
    "path.validator": "Path validation service",
    "path_alias.manager": "Path alias manager",
    "router": "Router service",
    "url_generator": "URL generator service",
}

@server.feature(TEXT_DOCUMENT_COMPLETION)
def complete_services(ls: LanguageServer, params: CompletionParams) -> CompletionList:
    doc = ls.workspace.get_text_document(params.text_document.uri)
    line = doc.lines[params.position.line]
    
    # Check if we're in a service call context
    if "::service(" in line or "->get(" in line:
        items = [
            CompletionItem(
                label=service_id,
                kind=CompletionItemKind.Constant,
                detail=f"Drupal Service: {description}",
                documentation=f"```php\n\\Drupal::service('{service_id}')\n```\n\n{description}",
                insert_text=service_id,
                filter_text=service_id,
                sort_text=f"0_{service_id}",  # Sort to top
            )
            for service_id, description in DRUPAL_SERVICES.items()
        ]
        return CompletionList(is_incomplete=False, items=items)
    
    return CompletionList(is_incomplete=False, items=[])
```

### Example 3: Go to Service Definition

```python
from lsprotocol.types import (
    TEXT_DOCUMENT_DEFINITION,
    DefinitionParams,
    Location,
    LocationLink,
)
from pathlib import Path
import yaml
import re

def find_service_definition(workspace_root: Path, service_id: str):
    """Find service definition in *.services.yml files."""
    for services_file in workspace_root.rglob("*.services.yml"):
        try:
            with open(services_file) as f:
                data = yaml.safe_load(f)
                if data and "services" in data:
                    if service_id in data["services"]:
                        service_def = data["services"][service_id]
                        class_name = service_def.get("class", "")
                        
                        # Find the class file
                        if class_name:
                            class_file = find_class_file(workspace_root, class_name)
                            if class_file:
                                return class_file
                        
                        # Return services.yml location if class not found
                        return services_file
        except Exception:
            continue
    return None

@server.feature(TEXT_DOCUMENT_DEFINITION)
def goto_definition(ls: LanguageServer, params: DefinitionParams):
    doc = ls.workspace.get_text_document(params.text_document.uri)
    line = doc.lines[params.position.line]
    
    # Extract service ID from line like: \Drupal::service('entity_type.manager')
    match = re.search(r'''['"]([\w\.]+)['"]''', line)
    if match:
        service_id = match.group(1)
        
        # Find workspace root
        workspace_root = Path(params.text_document.uri.replace("file://", "")).parent
        while not (workspace_root / "composer.json").exists():
            workspace_root = workspace_root.parent
            if workspace_root == workspace_root.parent:
                break
        
        # Find service definition
        service_file = find_service_definition(workspace_root, service_id)
        if service_file:
            return Location(
                uri=f"file://{service_file}",
                range=Range(
                    start=Position(line=0, character=0),
                    end=Position(line=0, character=0)
                )
            )
    
    return None
```

### Example 4: Show Hook Signature on Hover

```python
from lsprotocol.types import Hover, MarkupContent, MarkupKind

HOOK_SIGNATURES = {
    "hook_form_alter": {
        "signature": "hook_form_alter(&$form, \\Drupal\\Core\\Form\\FormStateInterface $form_state, $form_id)",
        "params": [
            ("$form", "array", "Nested array of form elements"),
            ("$form_state", "FormStateInterface", "The current state of the form"),
            ("$form_id", "string", "String representing the name of the form itself"),
        ],
        "return": "void",
        "group": "Form API",
        "file": "core/lib/Drupal/Core/Form/form.api.php",
    },
    "hook_cron": {
        "signature": "hook_cron()",
        "params": [],
        "return": "void",
        "description": "Perform periodic actions",
        "group": "System",
        "file": "core/core.api.php",
    },
}

@server.feature(TEXT_DOCUMENT_HOVER)
def hover_hook_info(ls: LanguageServer, params: HoverParams) -> Hover | None:
    doc = ls.workspace.get_text_document(params.text_document.uri)
    line = doc.lines[params.position.line]
    
    # Get word at position
    word = get_word_at_position(line, params.position.character)
    
    if word in HOOK_SIGNATURES:
        hook = HOOK_SIGNATURES[word]
        
        # Build markdown documentation
        md = f"### {word}\n\n"
        md += f"**Group:** {hook['group']}\n\n"
        
        md += "**Signature:**\n```php\n"
        md += f"function MYMODULE_{word}("
        md += ", ".join(p[0] for p in hook['params'])
        md += ")\n```\n\n"
        
        if hook['params']:
            md += "**Parameters:**\n"
            for param_name, param_type, param_desc in hook['params']:
                md += f"- `{param_name}` (*{param_type}*) - {param_desc}\n"
            md += "\n"
        
        md += f"**Returns:** `{hook['return']}`\n\n"
        md += f"**Defined in:** `{hook['file']}`\n"
        
        return Hover(
            contents=MarkupContent(kind=MarkupKind.Markdown, value=md)
        )
    
    return None
```

### Example 5: Code Actions for Quick Fixes

```python
from lsprotocol.types import (
    TEXT_DOCUMENT_CODE_ACTION,
    CodeAction,
    CodeActionKind,
    CodeActionParams,
    WorkspaceEdit,
    TextEdit,
)

@server.feature(TEXT_DOCUMENT_CODE_ACTION)
def code_actions(ls: LanguageServer, params: CodeActionParams) -> List[CodeAction]:
    doc = ls.workspace.get_text_document(params.text_document.uri)
    actions = []
    
    # Check each diagnostic in the range
    for diagnostic in params.context.diagnostics:
        if diagnostic.code == "deprecated":
            # Extract function name from message
            match = re.match(r"(\w+)\(\) is deprecated", diagnostic.message)
            if match:
                old_func = match.group(1)
                
                # Get replacement from our database
                if old_func in DEPRECATED_FUNCTIONS:
                    replacement = DEPRECATED_FUNCTIONS[old_func]["replacement"]
                    
                    # Create code action to replace it
                    actions.append(
                        CodeAction(
                            title=f"Replace with {replacement}",
                            kind=CodeActionKind.QuickFix,
                            diagnostics=[diagnostic],
                            edit=WorkspaceEdit(
                                changes={
                                    params.text_document.uri: [
                                        TextEdit(
                                            range=diagnostic.range,
                                            new_text=replacement
                                        )
                                    ]
                                }
                            ),
                        )
                    )
    
    return actions
```

### Example 6: Document Symbols (Outline View)

```python
from lsprotocol.types import (
    TEXT_DOCUMENT_DOCUMENT_SYMBOL,
    DocumentSymbol,
    SymbolKind,
)
import re

@server.feature(TEXT_DOCUMENT_DOCUMENT_SYMBOL)
def document_symbols(ls: LanguageServer, params: DocumentSymbolParams) -> List[DocumentSymbol]:
    doc = ls.workspace.get_text_document(params.text_document.uri)
    symbols = []
    
    # Parse functions
    for match in re.finditer(r'^function\s+(\w+)\s*\(', doc.source, re.MULTILINE):
        func_name = match.group(1)
        start_line = doc.source[:match.start()].count('\n')
        
        # Find end of function (simplified - look for closing brace)
        end_pos = find_function_end(doc.source, match.end())
        end_line = doc.source[:end_pos].count('\n')
        
        # Determine if it's a hook
        is_hook = func_name.startswith(('hook_', 'mymodule_'))
        
        symbols.append(
            DocumentSymbol(
                name=func_name,
                kind=SymbolKind.Function,
                range=Range(
                    start=Position(line=start_line, character=0),
                    end=Position(line=end_line, character=0)
                ),
                selection_range=Range(
                    start=Position(line=start_line, character=match.start() - doc.source[:match.start()].rfind('\n') - 1),
                    end=Position(line=start_line, character=match.end() - doc.source[:match.start()].rfind('\n') - 1)
                ),
                detail="Drupal Hook" if is_hook else "Function",
            )
        )
    
    return symbols
```

## Debugging Tips

1. **Log everything**: Use `server.show_message_log()` liberally
2. **Test incrementally**: Add one feature at a time
3. **Use VS Code's LSP Inspector**: `Developer: Inspect Editor Tokens and Scopes`
4. **Check stdio**: The server communicates via stdin/stdout - don't use `print()`!
5. **Read pygls examples**: https://github.com/openlawlibrary/pygls/tree/main/examples

## Resources

- **LSP Specification**: https://microsoft.github.io/language-server-protocol/
- **pygls Documentation**: https://pygls.readthedocs.io/
- **pygls GitHub**: https://github.com/openlawlibrary/pygls
- **Drupal API**: https://api.drupal.org/

## Integrating with Phpactor Language Server

Yes! You can integrate your Drupal Language Server with Phpactor in several ways. This gives you the best of both worlds: Phpactor's powerful PHP analysis + your Drupal-specific features.

### Strategy 1: Run Both Language Servers (Recommended)

The simplest and most maintainable approach is to run **both language servers simultaneously**. Most editors support multiple LSP servers for the same file type.

#### How It Works

```
┌─────────────┐
│   Editor    │
│  (VS Code,  │
│  Neovim)    │
└──────┬──────┘
       │
       ├──────────────┐
       │              │
   ┌───▼────┐    ┌───▼────┐
   │Phpactor│    │DrupalLS│
   │        │    │        │
   │General │    │Drupal  │
   │PHP     │    │Specific│
   └────────┘    └────────┘
```

**Benefits:**
- ✅ No code changes needed
- ✅ Each server does what it's best at
- ✅ Easy to maintain
- ✅ Can disable either server independently

**Phpactor provides:**
- General PHP completion (classes, methods, properties)
- Go to definition for PHP classes
- Refactoring tools
- Type inference
- Code navigation

**Your Drupal LS provides:**
- Drupal hook completion
- Service ID completion
- Drupal API documentation
- Drupal-specific diagnostics
- Config key validation

### Strategy 2: Create a Phpactor Extension

Create a Phpactor extension that adds Drupal-specific features directly to Phpactor.

#### Pros & Cons

**Pros:**
- Single language server process
- Tighter integration with Phpactor's features
- Can reuse Phpactor's PHP parsing

**Cons:**
- Must write PHP code (Phpactor is PHP-based)
- More complex to maintain
- Tied to Phpactor's release cycle

### Strategy 3: Proxy/Wrapper Server

Create a wrapper that combines both servers and presents a unified interface.

**Complexity:** High - Not recommended unless you have specific needs

---

## Implementation: Running Both Servers

### For VS Code

Create `.vscode/settings.json`:

```json
{
  // Phpactor configuration (via intelephense or phpactor extension)
  "intelephense.enable": true,
  
  // Or use Phpactor extension directly
  "phpactor.enable": true,
  
  // Add your Drupal LS
  "drupalls.enabled": true,
  "[php]": {
    // Enable both servers
    "editor.defaultFormatter": "bmewburn.vscode-intelephense-client"
  }
}
```

Or create a custom extension that starts both:

```typescript
// extension.ts
import * as vscode from 'vscode';
import { LanguageClient, LanguageClientOptions, ServerOptions } from 'vscode-languageclient/node';

export function activate(context: vscode.ExtensionContext) {
  // Start Phpactor
  const phpactorServer: ServerOptions = {
    command: 'phpactor',
    args: ['language-server']
  };
  
  const phpactorClient = new LanguageClient(
    'phpactor',
    'Phpactor',
    phpactorServer,
    { documentSelector: [{ scheme: 'file', language: 'php' }] }
  );
  
  // Start DrupalLS
  const drupalServer: ServerOptions = {
    command: 'poetry',
    args: ['run', 'python', '-m', 'drupalls']
  };
  
  const drupalClient = new LanguageClient(
    'drupalls',
    'Drupal Language Server',
    drupalServer,
    { documentSelector: [{ scheme: 'file', language: 'php' }] }
  );
  
  // Start both
  phpactorClient.start();
  drupalClient.start();
}
```

### For Neovim

Using `nvim-lspconfig`:

```lua
local lspconfig = require('lspconfig')

-- Configure Phpactor
lspconfig.phpactor.setup{
  cmd = { 'phpactor', 'language-server' },
  filetypes = { 'php' },
  root_dir = function(fname)
    return lspconfig.util.root_pattern('composer.json', '.git')(fname)
  end,
}

-- Configure DrupalLS
lspconfig.drupalls.setup{
  cmd = { 'poetry', 'run', 'python', '-m', 'drupalls' },
  filetypes = { 'php' },
  root_dir = function(fname)
    return lspconfig.util.root_pattern('composer.json', '.git')(fname)
  end,
  -- Optional: only enable in Drupal projects
  on_new_config = function(config, root_dir)
    if vim.fn.filereadable(root_dir .. '/core/lib/Drupal.php') == 1 then
      return config
    end
    return nil
  end,
}

-- Both servers will now provide features for PHP files
```

### For Sublime Text

In `LSP.sublime-settings`:

```json
{
  "clients": {
    "phpactor": {
      "enabled": true,
      "command": ["phpactor", "language-server"],
      "selector": "source.php"
    },
    "drupalls": {
      "enabled": true,
      "command": ["poetry", "run", "python", "-m", "drupalls"],
      "selector": "source.php"
    }
  }
}
```

---

## Handling Feature Overlap

When running multiple servers, some features might overlap. Here's how to handle it:

### Completion

Both servers might provide completions. The editor will typically merge them:

```
User types: "\Drupal::ser"

Phpactor provides:
  - service (method from \Drupal class)

DrupalLS provides:
  - service('entity_type.manager') [with service IDs]
  - service('database')
  - ...

Editor shows: All completions merged
```

**Configuration:**
- Most editors merge automatically
- VS Code: Shows all, sorted by relevance
- Neovim: Can configure priority with `capabilities`

### Hover

Both servers might provide hover info. Editors handle this differently:

**VS Code:** Shows first response, or allows switching between sources
**Neovim:** Can configure which server to prefer
**Sublime:** First server wins, or can be configured

**Solution:** Make your hover info complementary:

```python
@server.feature(TEXT_DOCUMENT_HOVER)
def hover(ls, params):
    # Only provide Drupal-specific info
    if word.startswith('hook_'):
        return Hover(...)  # Drupal hook info
    if word in DRUPAL_SERVICES:
        return Hover(...)  # Drupal service info
    
    # Let Phpactor handle general PHP
    return None
```

### Go to Definition

Similar strategy - let Phpactor handle general PHP, you handle Drupal-specific:

```python
@server.feature(TEXT_DOCUMENT_DEFINITION)
def definition(ls, params):
    # Only handle Drupal service definitions
    if is_drupal_service_call(line):
        return find_service_definition(...)
    
    # Let Phpactor handle class/method definitions
    return None
```

---

## Smart Delegation Pattern

You can make your Drupal LS "smart" about when to respond:

```python
def should_handle_drupal(document, position):
    """Determine if this is a Drupal-specific context."""
    line = document.lines[position.line]
    
    # Drupal-specific patterns
    if any(pattern in line for pattern in [
        '\\Drupal::',
        'hook_',
        '->get(',  # Service from container
        '@',       # Service injection in YAML/annotations
    ]):
        return True
    
    # Check if we're in a .module file
    if document.uri.endswith('.module'):
        return True
    
    # Check if we're in a Drupal-specific directory
    if any(dir in document.uri for dir in [
        '/src/Plugin/',
        '/src/Controller/',
        '/config/',
    ]):
        return True
    
    return False

@server.feature(TEXT_DOCUMENT_COMPLETION)
def completions(ls, params):
    doc = ls.workspace.get_text_document(params.text_document.uri)
    
    # Only respond in Drupal contexts
    if not should_handle_drupal(doc, params.position):
        return CompletionList(is_incomplete=False, items=[])
    
    # Provide Drupal completions
    return get_drupal_completions(doc, params.position)
```

---

## Creating a Phpactor Extension (Alternative)

If you prefer a single server, you can create a Phpactor extension:

### 1. Create Extension Structure

```bash
composer init
composer require phpactor/container
composer require phpactor/completion-extension
```

**composer.json:**
```json
{
  "name": "yourname/phpactor-drupal",
  "type": "phpactor-extension",
  "autoload": {
    "psr-4": {
      "YourName\\PhpactorDrupal\\": "lib/"
    }
  },
  "extra": {
    "phpactor.extension_class": "YourName\\PhpactorDrupal\\DrupalExtension"
  }
}
```

### 2. Create Extension Class

**lib/DrupalExtension.php:**
```php
<?php

namespace YourName\PhpactorDrupal;

use Phpactor\Container\Extension;
use Phpactor\Container\ContainerBuilder;
use Phpactor\MapResolver\Resolver;

class DrupalExtension implements Extension
{
    public function load(ContainerBuilder $container): void
    {
        $container->register('drupal.completor', function($container) {
            return new DrupalCompletor();
        }, ['completion.completor' => []]);
    }

    public function configure(Resolver $schema): void
    {
        // Configuration options
    }
}
```

### 3. Create Completor

**lib/DrupalCompletor.php:**
```php
<?php

namespace YourName\PhpactorDrupal;

use Generator;
use Phpactor\Completion\Core\Completor;
use Phpactor\Completion\Core\Suggestion;
use Phpactor\TextDocument\ByteOffset;
use Phpactor\TextDocument\TextDocument;

class DrupalCompletor implements Completor
{
    public function complete(TextDocument $source, ByteOffset $offset): Generator
    {
        $text = $source->__toString();
        
        // Detect if we're in a Drupal context
        if (strpos($text, '\\Drupal::service(') !== false) {
            yield Suggestion::create('entity_type.manager');
            yield Suggestion::create('database');
            yield Suggestion::create('config.factory');
            // ... more services
        }
        
        if (preg_match('/function\s+\w+_hook_/', $text)) {
            yield Suggestion::createWithOptions('hook_form_alter', [
                'type' => 'f',
                'short_description' => 'Alter forms before rendering'
            ]);
            // ... more hooks
        }
    }
}
```

### 4. Install and Use

```bash
# In your Drupal project
composer require yourname/phpactor-drupal

# Phpactor will auto-discover the extension
phpactor language-server
```

---

## Comparison: Which Approach?

| Aspect | Both Servers | Phpactor Extension |
|--------|--------------|-------------------|
| **Ease of Setup** | ⭐⭐⭐⭐⭐ Easy | ⭐⭐⭐ Moderate |
| **Maintenance** | ⭐⭐⭐⭐⭐ Independent | ⭐⭐⭐ Coupled to Phpactor |
| **Language** | Python (keep current) | PHP (rewrite needed) |
| **Performance** | 2 processes | 1 process |
| **Flexibility** | ⭐⭐⭐⭐⭐ Very flexible | ⭐⭐⭐ Limited to Phpactor APIs |
| **Drupal Features** | ⭐⭐⭐⭐⭐ Full control | ⭐⭐⭐⭐ Good |
| **PHP Features** | ⭐⭐⭐⭐⭐ Phpactor's full power | ⭐⭐⭐⭐⭐ Phpactor's full power |

**Recommendation:** **Run both servers** - it's simpler, more maintainable, and gives you full flexibility.

---

## Testing Both Servers Together

Create a test PHP file:

**test.php:**
```php
<?php

// Test Phpactor (should work)
class MyClass {
  public function myMethod() {
    // typing $this-> should show methods
  }
}

// Test DrupalLS (should work)
function mymodule_form_alter(&$form, $form_state, $form_id) {
  // typing \Drupal::service(' should show services
  \Drupal::service('');
  
  // typing hook_ should suggest hooks
}
```

Open this file in your editor with both servers running:
1. Type `$this->` inside `myMethod` - Phpactor provides completions
2. Type `\Drupal::service('` - DrupalLS provides service IDs
3. Type `hook_` - DrupalLS provides hook suggestions

Both servers working together! 🎉

---

## Resources

- **Phpactor Documentation:** https://phpactor.readthedocs.io/
- **Phpactor Extensions:** https://github.com/phpactor/language-server-phpactor-extensions
- **LSP Specification:** https://microsoft.github.io/language-server-protocol/
- **Your DrupalLS Docs:** See `05-DEVELOPMENT_GUIDE.md` and `01-QUICK_START.md`
