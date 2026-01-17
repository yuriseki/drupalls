# DrupalLS

<div align="center">

**A Modern Language Server Protocol (LSP) Implementation for Drupal Development**

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![pygls](https://img.shields.io/badge/pygls-v2.0+-purple.svg)](https://github.com/openlawlibrary/pygls)

</div>

---

## 🚀 Features

DrupalLS brings intelligent IDE features to Drupal development through the Language Server Protocol:

### ✅ Implemented
- **Service Autocompletion** - Autocomplete Drupal service names in `\Drupal::service()` and `->get()` calls
- **Service Hover Information** - View service details, class names, and file locations on hover
- **Service Go-to-Definition** - Navigate from PHP code to service YAML definitions
- **Plugin Capability Architecture** - Extensible system for adding new LSP features
- **Workspace Cache System** - Fast in-memory caching with < 1ms lookups
- **Smart File Detection** - Automatic Drupal root detection and workspace scanning
- **Real-time Updates** - Cache invalidation on file changes for up-to-date information
- **Text Synchronization** - Real-time file tracking and updates

### 🔄 In Progress
- Service-to-Class Definition - Navigate from YAML service definitions to PHP class files (documented)
- Hook autocompletion (`hook_form_alter`, `hook_node_view`, etc.)
- Configuration schema validation
- Entity type awareness

### 📋 Planned
- Hook hover and go-to-definition
- Plugin annotation support
- Route autocompletion
- Form API field completion
- Twig template support
- Diagnostics and validation
- Code actions and quick fixes
- Signature help for Drupal APIs

---

## 📦 Installation

### Prerequisites
- Python 3.12 or higher
- [Poetry](https://python-poetry.org/docs/#installation) for dependency management

### Install DrupalLS

```bash
# Clone the repository
git clone https://github.com/yourusername/drupalls.git
cd drupalls

# Install dependencies
poetry install

# Verify installation
poetry run drupalls --version
```

---

## 🔧 Editor Setup

### Visual Studio Code

1. **Install DrupalLS**:
   ```bash
   poetry install
   ```

2. **Create VSCode extension configuration**:
   Create a file `.vscode/settings.json` in your Drupal project:
   ```json
   {
     "drupal.languageServer.enable": true,
     "drupal.languageServer.command": "/path/to/drupalls/.venv/bin/python",
     "drupal.languageServer.args": [
       "/path/to/drupalls/drupalls/main.py"
     ]
   }
   ```

3. **Alternative: Using a VSCode Extension**:
   If you prefer a dedicated extension, create `.vscode/extensions/drupalls/package.json`:
   ```json
   {
     "name": "drupalls-vscode",
     "version": "0.1.0",
     "engines": { "vscode": "^1.75.0" },
     "activationEvents": [
       "onLanguage:php",
       "onLanguage:yaml"
     ],
     "main": "./extension.js",
     "contributes": {
       "configuration": {
         "title": "DrupalLS",
         "properties": {
           "drupalls.enable": {
             "type": "boolean",
             "default": true,
             "description": "Enable DrupalLS"
           }
         }
       }
     }
   }
   ```
   
   **Note**: VSCode doesn't natively recognize `.module`, `.install`, and `.inc` as file types. You may need to add this to your VSCode settings:
   ```json
   {
     "files.associations": {
       "*.module": "php",
       "*.install": "php",
       "*.inc": "php",
       "*.theme": "php"
     }
   }
   ```

4. **Restart VSCode** and open a Drupal project

### Neovim

Using **nvim-lspconfig**:

1. **Install DrupalLS**:
   ```bash
   poetry install
   ```

2. **Configure in your Neovim config** (`~/.config/nvim/init.lua` or `~/.config/nvim/lua/lsp.lua`):

   ```lua
   local lspconfig = require('lspconfig')
   local configs = require('lspconfig.configs')
   
   -- Define DrupalLS if not already defined
   if not configs.drupalls then
     configs.drupalls = {
       default_config = {
         cmd = {
           '/path/to/drupalls/.venv/bin/python',
           '/path/to/drupalls/drupalls/main.py'
         },
         filetypes = { 'php', 'yaml', 'module', 'install', 'inc' },
         root_dir = function(fname)
           return lspconfig.util.root_pattern('composer.json', '.git')(fname)
         end,
         settings = {},
       },
     }
   end
   
   -- Setup DrupalLS
   lspconfig.drupalls.setup({
     on_attach = function(client, bufnr)
       -- Your custom on_attach function
       print("DrupalLS attached to buffer " .. bufnr)
     end,
     capabilities = require('cmp_nvim_lsp').default_capabilities(),
   })
   ```

3. **Alternative: Using Mason** (recommended):
   
   If you use [mason.nvim](https://github.com/williamboman/mason.nvim):
   
   ```lua
   -- In your mason setup
   require('mason-lspconfig').setup({
     ensure_installed = { 'drupalls' },  -- If available in Mason registry
   })
   ```

4. **Restart Neovim** and open a Drupal PHP file

### Other Editors

DrupalLS follows the LSP specification and works with any LSP-compatible editor:

- **Sublime Text**: Use [LSP package](https://github.com/sublimelsp/LSP)
- **Emacs**: Use [lsp-mode](https://github.com/emacs-lsp/lsp-mode)
- **Vim**: Use [vim-lsp](https://github.com/prabirshrestha/vim-lsp)

Configuration pattern:
```
Command: /path/to/drupalls/.venv/bin/python
Args: ["/path/to/drupalls/drupalls/main.py"]
Filetypes: php, yaml, module, install, inc
```

**Note**: Some editors may require you to associate Drupal-specific file extensions (`.module`, `.install`, `.inc`, `.theme`) with PHP language mode since they are PHP files.

---

## 🎯 Usage

Once installed and configured, DrupalLS automatically provides:

### Service Autocompletion
```php
// Type \Drupal::service(' and get completions
\Drupal::service('entity_type.manager');
                 ↑
                 Autocomplete shows all available services
```

### Hover Information
```php
// Hover over a service name to see details
\Drupal::service('entity_type.manager');
                 ↑
                 Shows: Class, file location, arguments, tags
```

### Go-to-Definition
```php
// Ctrl+Click on service name to jump to definition
\Drupal::service('logger.factory');
                 ↑
                 Navigates to: core/core.services.yml:123
```

### Smart Detection
- Automatically detects Drupal root in your workspace
- Scans `*.services.yml` files from core, modules, themes, profiles
- Updates cache when files change
- Sub-millisecond cache access times

---

## 🏗️ Architecture

DrupalLS uses a plugin-based architecture for extensibility:

```
DrupalLS Architecture
│
├── LSP Server (pygls v2)
│   ├── Handles LSP protocol communication
│   └── Registers capability handlers
│
├── Capability Manager
│   ├── Plugin architecture for LSP features
│   ├── Aggregates results from multiple handlers
│   └── Registered Capabilities:
│       ├── ServicesCompletionCapability
│       ├── ServicesHoverCapability
│       └── ServicesDefinitionCapability
│
├── Workspace Cache (in-memory)
│   ├── WorkspaceCache - Central cache manager
│   ├── ServicesCache - Parse *.services.yml files
│   ├── HooksCache - Parse hook definitions (planned)
│   └── ConfigCache - Parse config schemas (planned)
│
└── File System Utilities
    ├── Drupal root detection
    └── PSR-4 path resolution
```

**Key Design Principles:**
- **In-memory caching** for sub-millisecond access times (< 1ms)
- **Plugin architecture** for adding features without modifying core
- **Type-safe** with Python 3.12+ type hints
- **Async-first** using pygls v2 async/await patterns
- **Incremental updates** for file changes
- **Capability aggregation** for composable features

See [Architecture Documentation](docs/CAPABILITY_PLUGIN_ARCHITECTURE.md) for details.

---

## 📚 Documentation

### Getting Started
- [Quick Start Guide](QUICK_START.md) - Get up and running quickly
- [Development Guide](DEVELOPMENT_GUIDE.md) - Complete LSP feature reference (1400+ lines)
- [LSP Features Reference](LSP_FEATURES_REFERENCE.md) - Quick lookup table of all LSP features

### Architecture & Design
- [Capability Plugin Architecture](docs/CAPABILITY_PLUGIN_ARCHITECTURE.md) - Extensible LSP feature system
- [Workspace Cache Architecture](docs/WORKSPACE_CACHE_ARCHITECTURE.md) - In-memory caching design
- [Storage Strategy](STORAGE_STRATEGY.md) - Why in-memory vs SQLite

### Implementation Guides
- [Cache Usage](CACHE_USAGE.md) - How to use WorkspaceCache API
- [Cache Quick Reference](QUICK_REFERENCE_CACHE.md) - Quick cache API lookup
- [Completion with Cache](docs/COMPLETION_WITH_CACHE.md) - Building completion features
- [Service Class Definition Guide](docs/SERVICE_CLASS_DEFINITION_GUIDE.md) - YAML to PHP navigation
- [Drupal Root Detection](docs/DRUPAL_ROOT_DETECTION.md) - Finding Drupal projects
- [File Path Best Practices](docs/FILE_PATH_BEST_PRACTICES.md) - Working with paths

### For Contributors
- [AGENTS.md](AGENTS.md) - Project context for LLMs and documentation writers

---

## 🧪 Development

### Setup Development Environment

```bash
# Install with dev dependencies
poetry install --with dev

# Run tests
poetry run pytest

# Run with debugging
poetry run python -m debugpy --listen 5678 --wait-for-client drupalls/main.py
```

### Project Structure

```
drupalls/
├── lsp/
│   ├── server.py                      # LSP server setup and initialization
│   └── capabilities/
│       ├── capabilities.py            # Base classes and CapabilityManager
│       └── services_capabilities.py   # Service completion/hover/definition
├── workspace/
│   ├── cache.py                       # Base classes (CachedWorkspace, WorkspaceCache)
│   ├── services_cache.py              # ServicesCache implementation
│   └── utils.py                       # File utilities (hash calculation, etc.)
├── utils/
│   └── find_files.py                  # Drupal root detection
└── main.py                            # Entry point
```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=drupalls

# Run specific test file
poetry run pytest tests/test_workspace_cache.py
```

### Adding New Features

DrupalLS uses a plugin architecture that makes adding new features straightforward:

1. **Create a cache** (if needed) in `drupalls/workspace/`:
   - Extend `CachedWorkspace` base class
   - Implement scanning and parsing logic
   - Add to `WorkspaceCache.caches` dict

2. **Create a capability** in `drupalls/lsp/capabilities/`:
   - Extend `CompletionCapability`, `HoverCapability`, or `DefinitionCapability`
   - Implement `can_handle()` to check context
   - Implement feature method (`complete()`, `hover()`, `definition()`)

3. **Register in CapabilityManager**:
   - Add to `capabilities` dict in `CapabilityManager.__init__()`
   - Capability is automatically discovered and used

4. **Write tests** in `tests/`:
   - Test cache parsing
   - Test capability `can_handle()` logic
   - Test feature implementation

See [CAPABILITY_PLUGIN_ARCHITECTURE.md](docs/CAPABILITY_PLUGIN_ARCHITECTURE.md) for detailed examples.

---

## 🤝 Integration with Phpactor

DrupalLS is designed to work **alongside** [Phpactor](https://github.com/phpactor/phpactor):

- **Phpactor**: General PHP language features (refactoring, class navigation, etc.)
- **DrupalLS**: Drupal-specific features (services, hooks, config, entities)

Both can run simultaneously - your editor will merge their capabilities.

---

## 🐛 Troubleshooting

### Language server not starting

```bash
# Check Python version
python --version  # Should be 3.12+

# Verify installation
poetry run drupalls --version

# Check logs (if your editor supports LSP logging)
# VSCode: Output > DrupalLS
# Neovim: :LspLog
```

### No completions appearing

1. Ensure you're in a Drupal project (has `core/` or `composer.json`)
2. Check LSP logs for Drupal root detection message
3. Verify `*.services.yml` files exist in your project

### Cache not updating

- Save the file (triggers `didChange` notification)
- Restart the language server
- Check if file is within Drupal root

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with [pygls](https://github.com/openlawlibrary/pygls) - Python Language Server Protocol framework
- Inspired by [Phpactor](https://github.com/phpactor/phpactor) - PHP language server
- Thanks to the Drupal community for comprehensive documentation

---

## 🗺️ Roadmap

**v0.2.0** (Current)
- ✅ Service completion, hover, and definition (PHP → YAML)
- ✅ Plugin capability architecture
- ✅ Workspace cache system
- ✅ Text synchronization
- 🔄 Service-to-class definition (YAML → PHP) - documented
- 🔄 Hook completion and hover

**v0.3.0**
- Hook go-to-definition
- Configuration schema parsing
- Config validation and completion
- Entity type awareness

**v0.4.0**
- Plugin annotation support
- Route autocompletion
- Form API field completion
- Diagnostics and validation

**v0.5.0**
- Code actions and quick fixes
- Signature help for Drupal APIs
- Document and workspace symbols

**v1.0.0**
- Full Drupal 10/11 support
- Twig template support
- Advanced refactoring capabilities
- Performance optimizations

---

<div align="center">

**[Report Bug](https://github.com/yourusername/drupalls/issues)** • **[Request Feature](https://github.com/yourusername/drupalls/issues)** • **[Contribute](CONTRIBUTING.md)**

Made with ❤️ for the Drupal community

</div>
