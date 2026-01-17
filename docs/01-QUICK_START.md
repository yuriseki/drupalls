# Drupal Language Server - Quick Start

## What We Built

A working Language Server Protocol implementation for Drupal using pygls v2 with:

✅ **Text Synchronization** - Tracks open files and changes
✅ **Autocomplete** - Suggests Drupal hooks and services
✅ **Hover Information** - Shows documentation for Drupal APIs
✅ **Extensible Architecture** - Easy to add more features

## File Structure

```
drupalls/
├── __main__.py                    # Entry point
├── lsp/
│   ├── server.py                  # Server creation
│   ├── capabilities.py            # LSP capabilities list
│   └── features/
│       ├── text_sync.py          # Document tracking
│       ├── completion.py         # Autocomplete
│       └── hover.py              # Hover info
test/
└── test_server_basic.py          # Basic tests
```

## How It Works

### 1. Server Creation (`drupalls/lsp/server.py`)

```python
from pygls.lsp.server import LanguageServer

server = LanguageServer("drupalls", "0.1.0")
```

The `LanguageServer` class handles all JSON-RPC communication with editors.

### 2. Feature Registration

Features are registered using decorators:

```python
@server.feature(TEXT_DOCUMENT_COMPLETION)
def completions(ls: LanguageServer, params: CompletionParams):
    # Return completion items
    return CompletionList(items=[...])
```

### 3. Editor Communication

```
User types in editor
    ↓
Editor sends JSON-RPC request
    ↓
Server handler processes request
    ↓
Server returns results
    ↓
Editor displays to user
```

## Running the Server

### Test that it works:
```bash
poetry run python -m drupalls
```
(It will wait for input - press Ctrl+C to exit)

### Run tests:
```bash
poetry run pytest -v
```

## Current Features Explained

### Text Synchronization
**What:** Keeps server in sync with editor
**When triggered:** File open/close/change/save
**Implementation:** `drupalls/lsp/features/text_sync.py`

**Example:**
1. You open `mymodule.module` in VS Code
2. Editor sends `textDocument/didOpen` notification
3. Server stores document content
4. You type - editor sends `textDocument/didChange`
5. Server updates its copy of the content

### Completion (Autocomplete)
**What:** Suggests code as you type
**When triggered:** User types, or Ctrl+Space
**Implementation:** `drupalls/lsp/features/completion.py`

**Example:**
1. You type `hook_f` in a PHP file
2. Editor sends `textDocument/completion` request
3. Server detects you're typing a hook name
4. Server returns list of matching hooks:
   - hook_form_alter
   - hook_field_widget_form_alter
   - etc.
5. Editor shows suggestions

**Try adding:** Module names, entity types, field types

### Hover Information
**What:** Shows documentation on hover
**When triggered:** Mouse hover or keyboard shortcut
**Implementation:** `drupalls/lsp/features/hover.py`

**Example:**
1. You hover over `hook_form_alter`
2. Editor sends `textDocument/hover` request
3. Server looks up documentation
4. Server returns markdown with:
   - Function signature
   - Parameter descriptions
   - Link to API docs
5. Editor shows in popup

**Try adding:** More hooks, Drupal services, classes

## Adding New Features

### Example: Add a new Drupal hook to completion

Edit `drupalls/lsp/features/completion.py`:

```python
drupal_hooks = [
    ("hook_form_alter", "Alter forms before rendering"),
    ("hook_entity_presave", "Act before an entity is saved"),  # ← Add this
    # ... more hooks
]
```

### Example: Add hover info for a service

Edit `drupalls/lsp/features/hover.py`:

```python
drupal_hook_info = {
    "hook_form_alter": "...",
    "entity_type.manager": r"""                                    # ← Add this
**EntityTypeManager Service**

Manages entity type definitions.

```php
$manager = \Drupal::service('entity_type.manager');
$storage = $manager->getStorage('node');
```
""",
}
```

## Next Steps

### Immediate improvements:
1. **Better word detection** - Currently very basic
2. **Context awareness** - Detect if in function, class, etc.
3. **More completions** - Add services, configs, entity types
4. **More hover info** - Document all common Drupal APIs

### Medium term:
1. **Go to Definition** - Jump to service definitions
2. **Find References** - Find hook implementations
3. **Diagnostics** - Warn about deprecated functions
4. **Code Actions** - Quick fixes

### Advanced:
1. **Parse Drupal core** - Auto-generate completions from core
2. **Project-specific** - Index user's custom modules
3. **Template support** - Twig file support
4. **Plugin system** - Let users add custom rules

## Integration with Editors

### VS Code
Create a VS Code extension that starts the server.
Example: https://code.visualstudio.com/api/language-extensions/language-server-extension-guide

### Neovim
Use built-in LSP client:
```lua
vim.lsp.start({
  name = 'drupalls',
  cmd = {'poetry', 'run', 'python', '-m', 'drupalls'},
  root_dir = vim.fs.dirname(vim.fs.find({'composer.json'}, { upward = true })[1]),
})
```

### Other Editors
Any editor supporting LSP can use this server!
- Vim (with vim-lsp or coc.nvim)
- Emacs (with lsp-mode)
- Sublime Text (with LSP package)
- More: https://microsoft.github.io/language-server-protocol/implementors/tools/

## Key Concepts

### 1. Synchronous vs Asynchronous
pygls v2 uses async/await. All handlers can be async:
```python
@server.feature(TEXT_DOCUMENT_COMPLETION)
async def completions(ls, params):
    # Can use await here
    result = await some_async_operation()
    return result
```

### 2. Workspace
`server.workspace` contains all open documents:
```python
doc = server.workspace.get_text_document(uri)
print(doc.source)  # Full content
print(doc.lines)   # List of lines
```

### 3. Position and Range
Positions are 0-indexed:
```python
Position(line=0, character=5)  # Line 1, column 6 in editor
Range(
    start=Position(line=0, character=0),
    end=Position(line=0, character=10)
)
```

### 4. URIs
Files are identified by URIs:
```
file:///home/user/project/mymodule.module
```

Convert with:
```python
from pathlib import Path
from pygls.uris import from_fs_path, to_fs_path

uri = from_fs_path(Path("/path/to/file.php"))
path = Path(to_fs_path(uri))
```

## Debugging

### Enable logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Send messages to editor:
```python
server.show_message_log("Debug: Completion requested")
server.show_message("Visible message to user")
```

### Check what editor sends:
Look at the JSON-RPC messages. pygls logs them with DEBUG level.

## Common Issues

**Import Error:** `ImportError: cannot import name 'LanguageServer'`
- Fix: Use `from pygls.lsp.server import LanguageServer` (not `pygls.server`)

**No completions showing:**
- Check if handler is registered: `TEXT_DOCUMENT_COMPLETION in server.feature_manager._features`
- Check editor LSP client is configured correctly
- Look at server logs

**Hover not working:**
- Verify word detection logic in `get_word_at_position()`
- Check if word exists in hover info dictionary
- Test with known words first

## Resources

- **Full guide:** See `05-DEVELOPMENT_GUIDE.md`
- **pygls docs:** https://pygls.readthedocs.io/
- **LSP spec:** https://microsoft.github.io/language-server-protocol/
- **Drupal API:** https://api.drupal.org/

## Questions?

Read the detailed `05-DEVELOPMENT_GUIDE.md` for in-depth explanations of each component!
