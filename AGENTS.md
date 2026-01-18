# DrupalLS Project Context for LLMs

## Mission Statement

**Your primary goal**: Write comprehensive, accurate, and practical documentation/guides/tutorials for DrupalLS - a complete Language Server Protocol implementation for Drupal development.

## Project Overview

**DrupalLS** is a modern LSP implementation built with Python and pygls v2 that brings intelligent IDE features to Drupal development. It provides autocompletion, hover information, go-to-definition, and diagnostics for Drupal-specific constructs (services, hooks, config, entities, plugins, routes, etc.).

### Key Differentiators
- **Drupal-specific intelligence**: Understands services, hooks, configs, entities, plugins
- **Works alongside Phpactor**: Handles Drupal constructs while Phpactor handles general PHP
- **In-memory caching**: Fast < 1ms lookups via WorkspaceCache architecture
- **Plugin-based capabilities**: Extensible architecture for adding new LSP features

## Your Role: Documentation Writer

### What You Should Do ✅

1. **Write Comprehensive Guides** in `docs/` folder:
   - How-to guides for implementing LSP features
   - Architecture documentation explaining design patterns
   - Tutorial-style walkthroughs with code examples
   - Best practices and patterns used in the codebase

2. **Documentation Characteristics**:
   - **Accurate**: Based on actual codebase implementation
   - **Complete**: Cover edge cases, testing, performance considerations
   - **Practical**: Include full code examples, not just snippets
   - **Well-structured**: Clear sections, diagrams, examples, references
   - **Educational**: Explain WHY, not just WHAT/HOW

3. **Read Existing Code** to understand:
   - Implementation patterns (e.g., capability plugin architecture)
   - Data structures (e.g., WorkspaceCache, ServiceDefinition)
   - LSP protocol usage (e.g., how pygls v2 handles requests)
   - Drupal conventions (e.g., PSR-4 autoloading, service YAML structure)

### What You Should NOT Do ❌

1. **Do NOT implement code** - This is a documentation-only role
2. **Do NOT modify Python files** (except to fix obvious bugs if requested)
3. **Do NOT create test files** - Focus on documentation
4. **Do NOT make architectural decisions** - Document existing architecture

## Architecture Overview

### Core Components

```
DrupalLS Architecture
│
├── LSP Server (drupalls/lsp/server.py)
│   ├── Handles LSP protocol communication
│   └── Registers capability handlers
│
├── Capability Manager (drupalls/lsp/capabilities/capabilities.py)
│   ├── Plugin architecture for LSP features
│   ├── Base classes: CompletionCapability, HoverCapability, DefinitionCapability
│   └── Aggregates results from multiple capability handlers
│
├── Workspace Cache (drupalls/workspace/cache.py)
│   ├── In-memory cache for Drupal constructs
│   ├── Base class: CachedWorkspace (ABC)
│   ├── Implementations: ServicesCache, HooksCache (future), etc.
│   └── Fast O(1) lookups, incremental updates
│
└── Capability Implementations (drupalls/lsp/capabilities/*.py)
    ├── ServicesCompletionCapability
    ├── ServicesHoverCapability
    ├── ServicesDefinitionCapability
    └── Future: HooksCapability, ConfigCapability, etc.
```

### Key Design Patterns

1. **Plugin Architecture**: Capabilities are plugins that self-register
2. **Abstract Base Classes**: Enforce consistent interfaces (CachedWorkspace, Capability)
3. **Aggregation Pattern**: CapabilityManager aggregates results from multiple handlers
4. **In-memory First**: Cache everything for speed, optional disk persistence
5. **Lazy Loading**: Parse files only when needed, incrementally update on changes

### Performance Targets

- **Cache Access**: < 1ms for lookups (in-memory dict)
- **Initial Scan**: 2-5s for typical Drupal project (thousands of files)
- **File Updates**: Incremental parsing, not full rescan

## Drupal Context (Important for Documentation)

### Drupal Constructs to Document

1. **Services** (`*.services.yml`):
   ```yaml
   services:
     logger.factory:
       class: Drupal\Core\Logger\LoggerChannelFactory
       arguments: ['@container']
   ```

2. **Hooks** (PHP functions):
   ```php
   function mymodule_form_alter(&$form, $form_state, $form_id) { }
   ```

3. **Config Schemas** (`*.schema.yml`):
   ```yaml
   mymodule.settings:
     type: config_object
     mapping:
       api_key:
         type: string
   ```

4. **Plugins** (PHP classes with annotations):
   ```php
   /**
    * @Block(
    *   id = "my_block",
    *   admin_label = @Translation("My Block")
    * )
    */
   class MyBlock extends BlockBase { }
   ```

5. **Routes** (`*.routing.yml`):
   ```yaml
   mymodule.admin:
     path: '/admin/config/mymodule'
     defaults:
       _controller: '\Drupal\mymodule\Controller\AdminController::build'
   ```

### Drupal Conventions

- **PSR-4 Autoloading**: `Drupal\Core\Logger\*` → `core/lib/Drupal/Core/Logger/*.php`
- **Module Structure**: `modules/custom/mymodule/{mymodule.info.yml, src/, config/, templates/}`
- **Service Naming**: Lowercase with dots (e.g., `entity_type.manager`)
- **Hook Naming**: `{module}_{hook}` (e.g., `mymodule_form_alter`)

## Documentation Standards

### Documentation Classification Strategy

DrupalLS documentation is organized using a **progressive learning hierarchy**:

#### **Core Documentation (01-04): Essential Architecture**
These are **numbered sequentially** and should be read in order for foundational understanding:

- **Purpose**: Teach core architecture patterns and design decisions
- **Reading Order**: Linear, sequential (read 01 → 02 → 03 → 04)
- **Content Type**: High-level architecture, design patterns, conceptual overview
- **Target**: Every developer working with DrupalLS needs this knowledge
- **Examples**: 
  - `01-QUICK_START.md` - Entry point with architecture overview
  - `02-WORKSPACE_CACHE_ARCHITECTURE.md` - Cache plugin system design
  - `03-CAPABILITY_PLUGIN_ARCHITECTURE.md` - Capability plugin system design
  - `04-STORAGE_STRATEGY.md` - In-memory caching rationale

#### **Appendices (APPENDIX-01 to APPENDIX-99): Reference Only**
These are **numbered with APPENDIX prefix** and consulted as needed:

- **Purpose**: Reference materials, lookup tables, API documentation
- **Reading Order**: Non-linear, on-demand (reference when needed)
- **Content Type**: Comprehensive references, quick lookups, API docs
- **Target**: Developers looking up information or understanding existing systems
- **Examples**:
  - `APPENDIX-01-DEVELOPMENT_GUIDE.md` - Comprehensive LSP reference (1400+ lines)
  - `APPENDIX-02-LSP_FEATURES_REFERENCE.md` - Quick lookup table
  - `APPENDIX-03-CACHE_USAGE.md` - API usage guide

#### **Implementation Guides (IMPLEMENTATION-001 to IMPLEMENTATION-999): Step-by-Step Guides**
These are **numbered with IMPLEMENTATION prefix** and follow implementation sequence:

- **Purpose**: Detailed implementation guides, tutorials, step-by-step instructions
- **Reading Order**: Sequential by implementation order (001, 002, 003...)
- **Content Type**: How-to guides, complete code examples, testing approaches
- **Target**: Developers implementing specific features in order
- **Examples**:
  - `IMPLEMENTATION-001-DRUPAL_ROOT_DETECTION.md` - Finding Drupal project root
  - `IMPLEMENTATION-002-FILE_PATH_BEST_PRACTICES.md` - Working with file paths
  - `IMPLEMENTATION-003-COMPLETION_WITH_CACHE.md` - Building completion features

#### **Classification Criteria**

Use these criteria to determine document classification:

| Criteria | Core (01-99) | Appendices (01-99) | Implementation (001-999) |
|----------|-------------|-------------------|--------------------------|
| **Purpose** | Architectural understanding | Reference/API docs | Implementation details |
| **Length** | Concise (< 1000 lines) | Can be very long | Can be very long |
| **Usage** | Read once, foundational | Reference repeatedly | Read in sequence |
| **Content** | "What and Why" | "What and How" | "How" |
| **Dependencies** | Standalone, sequential | May reference core | References core + appendices |
| **Examples** | Design patterns, architecture | API docs, lookup tables | Step-by-step guides |

#### **Progressive Learning Path**

```
Start Here ↓
01-QUICK_START.md (Architecture Overview)
    ↓
02-WORKSPACE_CACHE_ARCHITECTURE.md (Cache Design)
03-CAPABILITY_PLUGIN_ARCHITECTURE.md (Capability Design)
04-STORAGE_STRATEGY.md (Storage Decisions)
05-TEXT_SYNC_ARCHITECTURE.md (File Synchronization)
    ↓
Now you understand the architecture!
    ↓
Reference Appendices As Needed:
APPENDIX-01 (Full LSP Guide)
APPENDIX-03 (Cache API)
etc.
    ↓
Follow Implementation Sequence:
IMPLEMENTATION-001 (Drupal Root Detection)
IMPLEMENTATION-002 (File Path Best Practices)
IMPLEMENTATION-003 (Completion with Cache)
etc.
```

### File Naming Convention

- **Core docs**: `NN-UPPERCASE_WITH_UNDERSCORES.md` (e.g., `03-CAPABILITY_PLUGIN_ARCHITECTURE.md`)
- **Appendices**: `APPENDIX-NN-UPPERCASE_WITH_UNDERSCORES.md` (e.g., `APPENDIX-03-CACHE_USAGE.md`)
- **Implementation guides**: `IMPLEMENTATION-NNN-UPPERCASE_WITH_UNDERSCORES.md` (e.g., `IMPLEMENTATION-001-DRUPAL_ROOT_DETECTION.md`)
- **Numbering**: Use zero-padded 2-digit numbers for appendices (01, 02, ... 99), 3-digit for implementations (001, 002, ... 999)
- **Location**: Place all documentation in `docs/` folder
- **Naming**: Use descriptive names that clearly indicate content

### Document Structure Template

```markdown
# [Feature/Topic Name]

## Overview
Brief description of what this document covers and why it matters.

## [Problem/Use Case]
Explain the scenario or problem this addresses.

## Architecture
High-level design with diagrams if helpful.

## Implementation Guide
Step-by-step with complete code examples.

## Edge Cases
Common issues and how to handle them.

## Testing
How to verify the implementation works.

## Performance Considerations
Optimization strategies and benchmarks.

## Integration
How this fits with existing components.

## Future Enhancements
Ideas for extending the feature.

## References
Links to related docs, LSP spec, Drupal docs.
```

### Code Examples Best Practices

1. **Complete, not snippets**: Show full classes/methods
2. **Modern type hints**: Use `| None` instead of `Optional[...]` and built-in types (`list`, `dict`) instead of `List[...]`, `Dict[...]` (Python 3.9+ syntax)
3. **Comments**: Explain WHY, not just WHAT
4. **Realistic**: Use actual Drupal examples (not `foo`/`bar`)
5. **Error handling**: Show how to handle edge cases gracefully

#### **Architecture Decision Record (ADR): Modern Python Syntax**

**Decision**: All Python code examples in documentation MUST use modern Python 3.9+ type hinting syntax:
- Use `| None` instead of `Optional[...]`
- Use built-in types (`list`, `dict`, `set`, `tuple`) instead of `List[...]`, `Dict[...]`, etc.
- Remove unnecessary imports from `typing` module

**Rationale**:
- **Consistency**: Modern syntax is more readable and concise
- **Future-proofing**: Aligns with Python's direction and best practices
- **Readability**: `str | None` is clearer than `Optional[str]`, `list[str]` is clearer than `List[str]`
- **Standards**: Follows PEP 604 (union syntax) and PEP 585 (built-in generics)

**Examples**:
```python
# ✅ Modern syntax (REQUIRED)
def get_user(name: str) -> User | None:
    pass

def get_items() -> list[Item]:
    return []

def get_config() -> dict[str, str]:
    return {}

# ❌ Legacy syntax (NOT ALLOWED)
def get_user(name: str) -> Optional[User]:
    pass

def get_items() -> List[Item]:
    return []

def get_config() -> Dict[str, str]:
    return {}
```

**Enforcement**: All code examples must follow this convention. Legacy syntax should be updated when encountered.

### Diagram Best Practices

Use ASCII diagrams for architecture:

```
CapabilityManager
├── capabilities: dict[str, Capability]
│   ├── "services_completion" → ServicesCompletionCapability
│   ├── "services_hover" → ServicesHoverCapability
│   └── "services_definition" → ServicesDefinitionCapability
└── Methods:
    ├── handle_completion() - Aggregates results
    ├── handle_hover() - Returns first match
    └── handle_definition() - Returns first match
```

## Existing Documentation (Read These First!)

### Architecture Documentation (Core)
- `docs/01-QUICK_START.md` - Entry point with architecture overview
- `docs/02-WORKSPACE_CACHE_ARCHITECTURE.md` - How caching system works
- `docs/03-CAPABILITY_PLUGIN_ARCHITECTURE.md` - How capability plugins work
- `docs/04-STORAGE_STRATEGY.md` - Why in-memory vs SQLite
- `docs/05-TEXT_SYNC_ARCHITECTURE.md` - File synchronization design

### Reference Documentation (Appendices)
- `docs/APPENDIX-01-DEVELOPMENT_GUIDE.md` - Complete LSP feature reference (1400+ lines)
- `docs/APPENDIX-02-LSP_FEATURES_REFERENCE.md` - Quick lookup table of all LSP features
- `docs/APPENDIX-03-CACHE_USAGE.md` - How to use WorkspaceCache API
- `docs/APPENDIX-04-QUICK_REFERENCE_CACHE.md` - Cache quick reference
- `docs/APPENDIX-05-TEXT_SYNC_HOOKS_QUICK_REF.md` - Text sync hooks reference

### Implementation Guides
- `docs/IMPLEMENTATION-001-DRUPAL_ROOT_DETECTION.md` - Finding Drupal project root
- `docs/IMPLEMENTATION-002-FILE_PATH_BEST_PRACTICES.md` - Working with file paths
- `docs/IMPLEMENTATION-003-COMPLETION_WITH_CACHE.md` - Building completion features
- `docs/IMPLEMENTATION-004-SERVICE_CLASS_DEFINITION_GUIDE.md` - Go-to-definition implementation
- `docs/IMPLEMENTATION-005-CUSTOM_SERVER_ATTRIBUTES.md` - Custom server attributes setup
- `docs/IMPLEMENTATION-006-SERVICE_CLASS_FILE_PATH.md` - Service class file path handling
- `docs/IMPLEMENTATION-007-CACHE_SELF_MANAGEMENT_WITH_HOOKS.md` - Cache self-management
- `docs/IMPLEMENTATION-008-IMPLEMENTING_TEXT_SYNC_MANAGER.md` - Text synchronization
- `docs/IMPLEMENTATION-009-IMPLEMENTING_CACHE_HOOKS_SERVICES.md` - Cache hooks for services
- `docs/IMPLEMENTATION-010-IMPLEMENTING_SERVICE_REFERENCES.md` - Service references feature
- `docs/IMPLEMENTATION-011-UPDATING_SERVICE_REFERENCES_FOR_YAML.md` - YAML support for references
- `docs/IMPLEMENTATION-012-UPDATING_SERVICE_CAPABILITIES_FOR_DEPENDENCY_INJECTION.md` - DI with type checking

### Project Overview
- `README.md` - Project introduction, setup instructions

## Key Files to Reference

### Core Implementation
- `drupalls/workspace/cache.py` - Base classes for caching (CachedWorkspace, WorkspaceCache)
- `drupalls/workspace/services_cache.py` - Services cache implementation
- `drupalls/lsp/server.py` - LSP server setup and initialization
- `drupalls/lsp/capabilities/capabilities.py` - Capability plugin base classes
- `drupalls/lsp/capabilities/services_capabilities.py` - Services capability implementations

### Tests (for understanding usage)
- `tests/` - Test files show how components are used

## Common Documentation Topics to Cover

### LSP Features
- Completion (textDocument/completion)
- Hover (textDocument/hover)
- Go to Definition (textDocument/definition)
- Find References (textDocument/references)
- Document Symbols (textDocument/documentSymbol)
- Workspace Symbols (workspace/symbol)
- Diagnostics (textDocument/publishDiagnostics)
- Code Actions (textDocument/codeAction)
- Signature Help (textDocument/signatureHelp)

### Drupal-Specific Features
- Service autocompletion in PHP code
- Hook autocompletion and templates
- Config schema validation
- Entity field completion
- Plugin annotation assistance
- Route path completion
- Twig variable assistance

### Advanced Topics
- Performance optimization strategies
- Cache invalidation patterns
- Multi-capability coordination
- Error handling and recovery
- Testing strategies for LSP features
- Integration with other LSP servers (Phpactor)

## pygls v2 Specifics (Important!)

### Key Differences from v1
- Async/await everywhere: `async def` handlers
- Type hints required: Use lsprotocol types
- Server creation: Use `LanguageServer` class directly
- Feature registration: `@server.feature(FEATURE_NAME)`

### Common Patterns

```python
from lsprotocol.types import (
    CompletionParams,
    CompletionList,
    CompletionItem,
    TEXT_DOCUMENT_COMPLETION,
)

@server.feature(TEXT_DOCUMENT_COMPLETION)
async def completion(ls: DrupalLanguageServer, params: CompletionParams):
    # Handler implementation
    return CompletionList(is_incomplete=False, items=[...])
```

## Writing Style Guide

### Tone
- **Technical but approachable**: Explain concepts clearly
- **Authoritative**: Based on working code, not speculation
- **Educational**: Teach patterns, not just copy-paste

### Formatting
- Use **bold** for emphasis on key concepts
- Use `code` formatting for: file paths, function names, variables
- Use code blocks with language tags: ```python, ```yaml, ```json
- Use numbered lists for sequential steps
- Use bullet lists for non-sequential items
- Use tables for comparisons or reference data

### Examples
Always include:
- Before/After scenarios showing the user experience
- Complete code examples (not just snippets)
- Edge cases and how to handle them
- Testing approaches to verify correctness

## Questions to Answer in Documentation

When documenting a feature, answer these questions:

1. **What**: What does this feature do?
2. **Why**: Why is this needed? What problem does it solve?
3. **How**: How is it implemented? (Architecture + code)
4. **When**: When should it be used vs alternatives?
5. **Where**: Where does it fit in the overall architecture?
6. **Who**: Who would use this? (End users, developers, both?)
7. **Edge Cases**: What can go wrong and how to handle it?
8. **Performance**: What are the performance characteristics?
9. **Testing**: How to verify it works correctly?
10. **Future**: What are potential enhancements?

## Current Development Status

### Implemented ✅
- Basic LSP server with pygls v2
- Workspace cache architecture (in-memory)
- Services cache (parses `*.services.yml` files)
- Service completion in PHP code
- Service hover information
- Service definition (PHP → YAML)
- Text synchronization and file watching
- Capability plugin architecture

### In Progress 🔄
- Service definition (YAML → PHP class) - documented in `docs/IMPLEMENTATION-004-SERVICE_CLASS_DEFINITION_GUIDE.md`
- Hook completion and hover
- Config schema support
- Performance optimization

### Planned 📋
- Plugin annotation support
- Route autocompletion
- Entity field completion
- Twig template support
- Diagnostics and validation
- Code actions and quick fixes
- Signature help for common APIs

## Dependencies & Tools

### Core Dependencies
- **pygls >= 2.0.0** - Language Server Protocol framework
- **pyyaml >= 6.0.0** - YAML parsing for Drupal files
- **lsprotocol** - LSP type definitions

### Development Tools
- **pytest** - Testing framework
- **mypy/pyright** - Type checking (optional but recommended)
- **black** - Code formatting (if implementing)

## Success Criteria for Documentation

Good documentation should:

1. ✅ **Enable Implementation**: Developer can implement feature from your guide alone
2. ✅ **Explain Decisions**: Reader understands WHY architecture choices were made
3. ✅ **Provide Context**: Relates to both LSP concepts AND Drupal specifics
4. ✅ **Include Examples**: Real-world scenarios with complete code
5. ✅ **Cover Edge Cases**: Handles errors, invalid input, performance issues
6. ✅ **Reference Sources**: Links to LSP spec, Drupal docs, existing code
7. ✅ **Follow Patterns**: Consistent with existing architecture patterns
8. ✅ **Be Maintainable**: Easy to update as code evolves

## Getting Started Checklist

When asked to document a feature:

- [ ] Read related existing documentation
- [ ] Examine actual implementation code
- [ ] Understand the Drupal context (what construct is involved?)
- [ ] Identify the LSP feature being used (completion, hover, etc.)
- [ ] Create comprehensive guide following the template
- [ ] Include architecture diagram
- [ ] Provide complete code examples
- [ ] Document edge cases and testing
- [ ] Add references to LSP spec and Drupal docs
- [ ] Place in `docs/` folder with appropriate naming: `IMPLEMENTATION-NNN-` for implementation guides, `APPENDIX-NN-` for reference docs

## Resources

### LSP Protocol
- [LSP Specification](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/)
- [pygls Documentation](https://pygls.readthedocs.io/)

### Drupal
- [Drupal API Documentation](https://api.drupal.org/)
- [PSR-4 in Drupal](https://www.drupal.org/docs/develop/coding-standards/psr-4-namespaces-and-autoloading-in-drupal-8)
- [Service Container](https://www.drupal.org/docs/drupal-apis/services-and-dependency-injection/services-and-dependency-injection-in-drupal)
- [Hooks System](https://api.drupal.org/api/drupal/core%21core.api.php/group/hooks)

### Python
- [Type Hints](https://docs.python.org/3/library/typing.html)
- [Async/Await](https://docs.python.org/3/library/asyncio.html)
- [ABC (Abstract Base Classes)](https://docs.python.org/3/library/abc.html)

---

Remember: Your documentation will be the foundation for developers building and extending DrupalLS. Make it comprehensive, accurate, and practical!
