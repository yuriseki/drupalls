# Routing Cache Implementation

## Overview

This document describes the implementation of a **routing cache** for DrupalLS, enabling fast, in-memory lookups of Drupal routes defined in `*.routing.yml` files. The routing cache supports Language Server Protocol (LSP) features such as autocompletion, go-to-definition, and hover for route names and paths in Drupal projects.

Routing is a core concept in Drupal, mapping URLs to controllers or callback functions. Efficiently parsing and caching route definitions is essential for providing real-time, context-aware IDE features.

## Problem/Use Case

### Scenario

- **Drupal developers** frequently reference and define routes in `*.routing.yml` files.
- IDE features like **route name autocompletion**, **go-to-definition**, and **hover documentation** require fast access to all available routes.
- Scanning and parsing YAML files on every request is slow and resource-intensive.

### Problem

- **Performance bottleneck**: Repeatedly parsing YAML files for every LSP request is inefficient.
- **Stale data**: Changes to routing files must be reflected immediately in the cache to avoid out-of-date suggestions.
- **Scalability**: Large Drupal projects may have hundreds of routes across many modules.

### Solution

- Implement a **RoutesCache** that:
  - Scans all `*.routing.yml` files in the workspace.
  - Parses and caches route definitions as `RouteDefinition` objects.
  - Integrates with the `WorkspaceCache` for efficient invalidation and updates.
  - Listens to text synchronization events for real-time cache updates.

## Architecture

The routing cache architecture follows the established pattern used for services caching, with adaptations for route-specific data.

```
RoutesCache
├── routes: dict[str, RouteDefinition]
│   ├── key: route name (e.g., "user.login")
│   └── value: RouteDefinition instance
├── scan_files() - Scans all *.routing.yml files
├── parse_routing_file(path) - Parses a single YAML file
├── update_from_text_sync(uri, text) - Updates cache on file change
└── get_route(name) - Returns RouteDefinition | None
    get_all_routes() - Returns list[RouteDefinition]

RouteDefinition (dataclass)
├── name: str                          # Route name (e.g., "user.login")
├── path: str                          # URL path (e.g., "/user/login")
├── methods: list[str]                 # HTTP methods (default: ["GET"])
├── defaults: dict[str, str]           # Route defaults (_controller, _form, _title, etc.)
├── requirements: dict[str, str]       # Route requirements (_permission, _module_dependencies, etc.)
├── file: str                          # Source file path
└── line: int                          # Line number in file

# Convenience properties:
├── controller -> str | None           # _controller from defaults
├── form -> str | None                 # _form from defaults
├── title -> str | None                # _title or _title_callback from defaults
├── permission -> str | None           # _permission from requirements
└── handler_class -> str | None        # Primary handler (controller or form)
```

**Integration Points:**
- **WorkspaceCache**: Manages lifecycle and invalidation.
- **Text Sync Hooks**: Updates cache on file changes.
- **LSP Capabilities**: Provides route data for completion, hover, etc.

## Implementation Guide

### 1. RouteDefinition Dataclass

Define a comprehensive dataclass to represent a single route, capturing all Drupal routing metadata.

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class RouteDefinition(CachedDataBase):
    # Core route data
    name: str
    path: str
    methods: list[str] = field(default_factory=list)
    defaults: dict[str, str] = field(default_factory=dict)
    requirements: dict[str, str] = field(default_factory=dict)
    file: str = ""
    line: int = 1

    def __post_init__(self):
        # Defensive: Ensure collections are always proper types
        if self.methods is None:
            object.__setattr__(self, 'methods', [])
        if self.defaults is None:
            object.__setattr__(self, 'defaults', {})
        if self.requirements is None:
            object.__setattr__(self, 'requirements', {})

    @property
    def controller(self) -> str | None:
        """Get the controller if this route has one."""
        return self.defaults.get('_controller')

    @property
    def form(self) -> str | None:
        """Get the form class if this route has one."""
        return self.defaults.get('_form')

    @property
    def title(self) -> str | None:
        """Get the title (static or callback)."""
        return self.defaults.get('_title') or self.defaults.get('_title_callback')

    @property
    def permission(self) -> str | None:
        """Get the required permission if any."""
        return self.requirements.get('_permission')

    @property
    def handler_class(self) -> str | None:
        """Get the primary handler class (controller or form)."""
        return self.controller or self.form
```

**Why:**
- **Comprehensive**: Captures all Drupal route metadata (controllers, forms, titles, permissions, etc.)
- **Flexible**: Uses dictionaries for `defaults` and `requirements` to handle any custom keys
- **Convenient**: Properties provide easy access to common fields
- **Extensible**: Can handle future Drupal routing features

---

### 2. RoutesCache Class

Implement the main cache class, following the pattern from `ServicesCache`.

```python
import os
import yaml
from pathlib import Path
from drupalls.workspace.cache import WorkspaceCache

class RoutesCache(WorkspaceCache):
    def __init__(self, workspace_root: str):
        super().__init__(workspace_root)
        self.routes: dict[str, RouteDefinition] = {}

    def scan_files(self) -> None:
        """Scan all *.routing.yml files and populate the cache."""
        self.routes.clear()
        for yml_path in Path(self.workspace_root).rglob("*.routing.yml"):
            self._parse_routing_file(str(yml_path))

    def _parse_routing_file(self, file_path: str) -> None:
        """Parse a single routing YAML file and update the cache."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                return  # Defensive: skip invalid files

            for i, (route_name, route_info) in enumerate(data.items()):
                path = route_info.get("path", "")
                methods = route_info.get("methods", ["GET"])
                if isinstance(methods, str):
                    methods = [methods]
                defaults = route_info.get("defaults", {})
                requirements = route_info.get("requirements", {})
                # Find line number for the route in the file (optional, for go-to-definition)
                line = self._find_route_line(content, route_name)
                self.routes[route_name] = RouteDefinition(
                    name=route_name,
                    path=path,
                    methods=methods,
                    defaults=defaults,
                    requirements=requirements,
                    file=file_path,
                    line=line,
                )
        except Exception as e:
            # Log and skip file on error
            print(f"Error parsing {file_path}: {e}")

    def _find_route_line(self, content: str, route_name: str) -> int:
        """Find the line number where the route is defined (1-based)."""
        for idx, line in enumerate(content.splitlines(), 1):
            if line.strip().startswith(f"{route_name}:"):
                return idx
        return 1  # Default to top if not found

    def get_route(self, name: str) -> RouteDefinition | None:
        return self.routes.get(name)

    def get_all_routes(self) -> list[RouteDefinition]:
        return list(self.routes.values())

    def update_from_text_sync(self, uri: str, text: str) -> None:
        """Update cache when a routing file is changed in the editor."""
        if uri.endswith(".routing.yml"):
            self._parse_routing_text(uri, text)

    def _parse_routing_text(self, uri: str, text: str) -> None:
        """Parse YAML text from an open document and update the cache."""
        try:
            data = yaml.safe_load(text)
            if not isinstance(data, dict):
                return
            for route_name, route_info in data.items():
                path = route_info.get("path", "")
                methods = route_info.get("methods", ["GET"])
                if isinstance(methods, str):
                    methods = [methods]
                controller = route_info.get("defaults", {}).get("_controller")
                # Line number not available from text sync; set to 1
                self.routes[route_name] = RouteDefinition(
                    name=route_name,
                    path=path,
                    methods=methods,
                    controller=controller,
                    file=uri,
                    line=1,
                )
        except Exception as e:
            print(f"Error parsing routing text from {uri}: {e}")
```

---

### 3. Scanning *.routing.yml Files

- Use `Path(workspace_root).rglob("*.routing.yml")` to find all routing files.
- Parse each file and extract route definitions.
- Store in the `routes` dictionary for fast lookup.

---

### 4. Integration with WorkspaceCache

- Inherit from `WorkspaceCache` for lifecycle management.
- Register the cache with the workspace so it is available to LSP capability providers.

---

### 5. Text Sync Hooks for Real-Time Updates

- Implement `update_from_text_sync(uri, text)` to update the cache when a routing file is edited in the IDE.
- This ensures that LSP features always reflect the latest unsaved changes.

---

## Edge Cases

- **Malformed YAML**: Skip files with syntax errors and log a warning.
- **Duplicate route names**: Last definition wins; routes are keyed by name.
- **Non-standard methods**: Accept both string and list for `methods`.
- **Missing fields**: Default `methods` to `["GET"]`, empty dicts for `defaults`/`requirements`.
- **Complex defaults**: Handle `_controller`, `_form`, `_title`, `_title_callback`, and custom keys.
- **Complex requirements**: Handle `_permission`, `_module_dependencies`, and custom requirements.
- **Route callbacks**: Skip `route_callbacks` entries (dynamic route generation).
- **File deletion**: Invalidate cache entry if a routing file is deleted.
- **Large files**: For very large YAML files, consider streaming parsing (not implemented here).

## Testing

### Verification Approaches

1. **Unit Tests**:
   - Test parsing of valid and invalid routing YAML files.
   - Test cache population and retrieval.
   - Test text sync updates with in-memory YAML strings.

2. **Integration Tests**:
   - Simulate workspace with multiple modules and routing files.
   - Verify LSP features (completion, hover) use the cache correctly.

3. **Edge Case Tests**:
   - Malformed YAML, duplicate routes, missing fields.

### Example Test Case

```python
import pytest

def test_parse_comprehensive_routing_file(tmp_path):
    yml_content = """
user.login:
  path: '/user/login'
  defaults:
    _controller: '\\Drupal\\user\\Controller\\UserController::login'
    _title: 'User Login'
  requirements:
    _permission: 'access content'
  methods: ['GET', 'POST']

admin.settings:
  path: '/admin/config/example'
  defaults:
    _form: '\\Drupal\\example\\Form\\SettingsForm'
    _title_callback: '\\Drupal\\example\\Form\\SettingsForm::getTitle'
  requirements:
    _permission: 'administer site configuration'
"""
    file_path = tmp_path / "example.routing.yml"
    file_path.write_text(yml_content)
    cache = RoutesCache(str(tmp_path))
    cache.scan_files()

    # Test controller route
    login_route = cache.get_route("user.login")
    assert login_route is not None
    assert login_route.path == "/user/login"
    assert login_route.methods == ["GET", "POST"]
    assert login_route.controller == "\\Drupal\\user\\Controller\\UserController::login"
    assert login_route.form is None
    assert login_route.title == "User Login"
    assert login_route.permission == "access content"

    # Test form route
    settings_route = cache.get_route("admin.settings")
    assert settings_route is not None
    assert settings_route.controller is None
    assert settings_route.form == "\\Drupal\\example\\Form\\SettingsForm"
    assert settings_route.title == "\\Drupal\\example\\Form\\SettingsForm::getTitle"
    assert settings_route.handler_class == "\\Drupal\\example\\Form\\SettingsForm"
```

## Performance Considerations

- **In-memory cache**: Ensures <1ms lookup for route definitions.
- **Batch scanning**: Only performed on cache initialization or full refresh.
- **Incremental updates**: Text sync hooks update only affected routes.
- **Disk persistence**: Optional JSON serialization speeds up server restarts.
- **Memory usage**: Scales with number of routes; negligible for typical projects.

## Integration

- **WorkspaceCache**: RoutesCache is registered and managed alongside other caches (e.g., ServicesCache).
- **Disk Persistence**: Routes are saved to `/.drupalls/cache/routes.json` for fast server restarts.
- **LSP Capabilities**: Route data is exposed to LSP features for completion, hover, go-to-definition.
- **Text Synchronization**: Real-time updates ensure IDE always reflects current routing state.

## Future Enhancements

- **File Deletion Handling**: Invalidate routes when files are deleted.
- **Route Usage Indexing**: Track where routes are referenced in codebase.
- **Advanced Metadata**: Parse requirements, permissions, and other route attributes.
- **Streaming YAML Parsing**: For very large files, optimize memory usage.

## References

- [Drupal Routing API](https://www.drupal.org/docs/drupal-apis/routing-system)
- [LSP Specification](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/)
- [pygls Documentation](https://pygls.readthedocs.io/)
- [Implementation Pattern: Services Cache](IMPLEMENTATION-009-IMPLEMENTING_CACHE_HOOKS_SERVICES.md)

## Next Steps

- Implement the `RoutesCache` class in `drupalls/workspace/routes_cache.py`.
- Register the cache in the workspace initialization.
- Integrate with LSP capability providers for route-based features.
- Write comprehensive tests for cache population and updates.