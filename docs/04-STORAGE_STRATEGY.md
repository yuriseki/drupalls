# Data Storage Architecture for DrupalLS

## Recommendation: In-Memory Cache with Optional Persistence

For a Drupal Language Server, **in-memory caching** is the recommended approach because:

1. ✅ Fast access (critical for LSP responsiveness)
2. ✅ Simple implementation
3. ✅ Sufficient for most projects (even large Drupal sites)
4. ✅ Easy to invalidate when files change
5. ✅ No database dependencies

**SQLite is generally NOT recommended** for LSP servers because:
- ❌ Slower than in-memory (adds latency to every completion)
- ❌ Adds complexity (schema, migrations, locking)
- ❌ Overkill for data that changes frequently
- ❌ Harder to invalidate cache properly

## Storage Architecture

```
┌─────────────────────────────────────────────────────┐
│  Language Server Process                            │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │  WorkspaceCache (singleton)                   │  │
│  │  ├─ services: Dict[str, ServiceDefinition]    │  │
│  │  ├─ hooks: Dict[str, HookDefinition]          │  │
│  │  ├─ config_schemas: Dict[str, ConfigSchema]   │  │
│  │  ├─ file_hashes: Dict[str, str]               │  │
│  │  └─ last_scan: datetime                       │  │
│  └───────────────────────────────────────────────┘  │
│           ↑                                         │
│           │ (populate on workspace init)            │
│           │ (invalidate on file changes)            │
│  ┌────────┴────────────────────────────────────┐    │
│  │  Scanner                                    │    │
│  │  ├─ scan_services_yaml()                    │    │
│  │  ├─ scan_hooks()                            │    │
│  │  └─ scan_config_schemas()                   │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

## Implementation Strategy

### 1. Create a Workspace Cache Manager

This manages all parsed data for the workspace.

**Location:** `drupalls/workspace/cache.py`

### 2. Scan and Parse on Initialization

When workspace is opened, scan once and populate cache.

### 3. Invalidate on File Changes

When `*.services.yml` changes, re-parse affected files.

### 4. Optional Disk Persistence

For large projects, cache to disk to speed up restarts (optional).

## When to Consider SQLite

Use SQLite only if:
- You need cross-session persistence (rare for LSP)
- You have very large codebases (100+ modules)
- You need complex queries across data
- You want to share data between multiple processes

For most Drupal projects, in-memory is sufficient and much faster.

## Recommended Solution: Hybrid Approach

1. **Primary:** In-memory cache (fast, always used)
2. **Optional:** Disk cache (JSON files in `.drupalls/cache/`)
3. **Fallback:** Re-parse if cache invalid

This gives you:
- Speed of in-memory
- Fast restarts via disk cache
- No database complexity
