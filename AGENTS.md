# DrupalLS Project Context

## Project Overview

**DrupalLS** is a Language Server Protocol implementation for Drupal development, built with Python and pygls v2. It provides intelligent IDE features (autocompletion, hover, go-to-definition, diagnostics) for Drupal-specific constructs.

### Key Features
- **Drupal-specific intelligence**: Services, hooks, configs, entities, plugins
- **Works alongside Phpactor**: DrupalLS handles Drupal, Phpactor handles general PHP
- **In-memory caching**: Fast < 1ms lookups via WorkspaceCache architecture
- **Plugin-based capabilities**: Extensible architecture for LSP features

## Agent System

This project uses OpenCode agents for orchestrated documentation work. Switch to the **core** agent (Tab key) for full functionality.

### Available Agents

| Agent | Type | Purpose |
|-------|------|---------|
| `core` | Primary | Orchestrates all documentation and implementation tasks |
| `@doc-writer` | Subagent | Creates documentation files |
| `@code-explorer` | Subagent | Investigates codebase (read-only) |
| `@lsp-expert` | Subagent | LSP protocol guidance |
| `@drupal-expert` | Subagent | Drupal conventions guidance |
| `@codeblocks` | Subagent | Validates code examples in docs |
| `@test-creator` | Subagent | Creates comprehensive pytest tests |
| `@code-implementer` | Subagent | Implements Python code from IMPLEMENTATION-*.md docs |

### Agent Definitions

Full agent instructions are in `.opencode/agents/`:
- `.opencode/agents/core.md` - Primary orchestrator
- `.opencode/agents/subagents/doc-writer.md` - Documentation writer
- `.opencode/agents/subagents/code-explorer.md` - Code explorer
- `.opencode/agents/subagents/lsp-expert.md` - LSP expert
- `.opencode/agents/subagents/drupal-expert.md` - Drupal expert
- `.opencode/agents/subagents/codeblocks.md` - Code block validator
- `.opencode/agents/subagents/test-creator.md` - Test file creator
- `.opencode/agents/subagents/code-implementer.md` - Code implementer

## Project Structure

```
DrupalLS/
├── drupalls/                    # Python source code
│   ├── lsp/                     # LSP server
│   │   ├── server.py            # Main server
│   │   └── capabilities/        # LSP capabilities
│   └── workspace/               # Workspace management
│       ├── cache.py             # Cache base classes
│       └── services_cache.py    # Services cache
├── docs/                        # Documentation (output)
├── drafts/                      # Code validation sandbox
├── tests/                       # Test files
└── .opencode/agents/            # Agent definitions
```

## Documentation System

### Classification

| Type | Prefix | Purpose | Example |
|------|--------|---------|---------|
| Core | `NN-` | Architecture (read sequentially) | `01-QUICK_START.md` |
| Appendix | `APPENDIX-NN-` | Reference (lookup as needed) | `APPENDIX-01-DEVELOPMENT_GUIDE.md` |
| Implementation | `IMPLEMENTATION-NNN-` | Step-by-step guides | `IMPLEMENTATION-001-DRUPAL_ROOT_DETECTION.md` |

### Document Template

See `@doc-writer` agent for the full template. Key sections:
- Overview, Problem/Use Case, Architecture
- Implementation Guide (with code examples)
- Edge Cases, Testing, Performance
- Integration, Future Enhancements, References

### Code Examples

All Python code must use modern 3.9+ syntax:
```python
# Required syntax
def get_service(name: str) -> Service | None:  # Not Optional[Service]
    return services.get(name)

def get_all() -> list[Service]:  # Not List[Service]
    return list(services.values())
```

All code blocks are validated via `@codeblocks` → sandbox files in `drafts/`.

## Workflow

### Documentation Task

```
1. User requests documentation
2. Core agent delegates to subagents:
   - @code-explorer → Investigate implementation
   - @lsp-expert → LSP protocol details
   - @drupal-expert → Drupal conventions
   - @doc-writer → Create documentation
   - @codeblocks → Validate code blocks
3. Core agent reviews and integrates
```

### Implementation Task

**IMPORTANT**: Only invoke `@code-implementer` when the user:
1. **Explicitly requests** code implementation (not documentation)
2. **Specifies a specific** `IMPLEMENTATION-*.md` document to implement from

```
1. User requests implementation from IMPLEMENTATION-*.md doc
   Example: "Implement code from IMPLEMENTATION-016-PHPACTOR_CONTEXT_AWARE_INTEGRATION.md"
2. Core agent delegates to @code-implementer:
   - Read implementation document
   - Create Python files in drupalls/
   - Verify syntax and imports
3. For each file created:
   - @test-creator → Create comprehensive tests
   - Run tests (.venv/bin/python -m pytest)
   - If tests fail → fix code or tests
   - Repeat until passing
4. Core agent reports final status
```

### Code Validation

```
@doc-writer creates doc with code examples
    ↓
@codeblocks extracts Python blocks
    ↓
Creates drafts/{doc}_{block}_{desc}.py
    ↓
Validates syntax and type hints
    ↓
Reports: ✅ VALID | ❌ INVALID | ⚠️ WARNING
    ↓
@doc-writer fixes issues
    ↓
Files remain in drafts/ permanently
```

## Key Constraints

- **Do NOT implement code directly** - use @code-implementer for implementation tasks
- **Do NOT make architectural decisions** - document existing
- **Always validate code blocks** before finalizing docs
- **Always use modern Python syntax** (3.9+)
- **Tests via @test-creator**: Mock only external deps, never internal functions
- **Always use `.venv/bin/python`** - never bare `python` commands

## Current Status

### Implemented
- LSP server with pygls v2
- Workspace cache architecture
- Services cache and capabilities
- Text synchronization

### In Progress
- Service definition (YAML → PHP class)
- Hook completion and hover
- Config schema support

### Planned
- Plugin annotation support
- Route autocompletion
- Entity field completion
- Twig template support
- Diagnostics and validation

## Resources

### Project Files
- `AGENTS-ORIGINAL.md` - Complete original context (563 lines)
- `README.md` - Project introduction

### External
- [LSP Specification](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/)
- [pygls Documentation](https://pygls.readthedocs.io/)
- [Drupal API](https://api.drupal.org/)

---

For detailed context, see `AGENTS-ORIGINAL.md`. For agent-specific instructions, see `.opencode/agents/`.
