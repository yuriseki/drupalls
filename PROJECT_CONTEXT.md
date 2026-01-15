# DrupalLS Project Context

## Project Overview
DrupalLS is a Language Server Protocol implementation for Drupal development using pygls v2.

## Current Status

### Completed
- ✅ Basic server infrastructure (pygls v2)
- ✅ Text synchronization features
- ✅ Basic completion (hooks, services)
- ✅ Basic hover information
- ✅ Workspace cache architecture (in-memory)
- ✅ Comprehensive documentation

### In Progress
- 🔄 Recreating features in `drupalls/features/`
- 🔄 Implementing service autocompletion using WorkspaceCache
- 🔄 Parsing *.services.yml files

### Architecture Decisions
- **Storage:** In-memory cache (NOT SQLite) - faster and simpler
- **Language:** Python with pygls v2
- **Integration:** Designed to work alongside Phpactor
- **Cache:** WorkspaceCache in `drupalls/workspace/cache.py`

## Important Notes
- **Documentation Only:** Do not implement code, only write guides/tutorials in .md files inside docs folder
- **Cache Strategy:** Use in-memory Dict, optional disk persistence via JSON
- **Performance:** Target < 1ms for cache access, 2-5s for initial scan

## Key Files
- `drupalls/workspace/cache.py` - Workspace cache implementation
- `drupalls/lsp/server.py` - Server setup
- `drupalls/features/` - Feature implementations
- `DEVELOPMENT_GUIDE.md` - Complete LSP reference
- `CACHE_USAGE.md` - Cache usage guide
- `STORAGE_STRATEGY.md` - Storage architecture

## Next Steps
1. Integrate WorkspaceCache with server initialization
2. Update service completion to use cache
3. Add cache invalidation to text_sync
4. Test with real Drupal project
5. Extend cache to parse hooks, config schemas, entity types

## Dependencies
- pygls >= 2.0.0
- pyyaml >= 6.0.0
- pytest (dev)

## Documentation Structure
- `README.md` - Project overview
- `QUICK_START.md` - Getting started
- `DEVELOPMENT_GUIDE.md` - Complete LSP feature reference (1400+ lines)
- `LSP_FEATURES_REFERENCE.md` - Quick lookup table
- `STORAGE_STRATEGY.md` - Why in-memory vs SQLite
- `CACHE_USAGE.md` - How to use WorkspaceCache
- `QUICK_REFERENCE_CACHE.md` - Cache quick reference

## Contact/References
- Phpactor integration documented in DEVELOPMENT_GUIDE.md
- All 40+ LSP features documented
- 6 practical Drupal examples included
