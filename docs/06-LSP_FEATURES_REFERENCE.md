# LSP Features Quick Reference

This is a quick lookup table for all LSP features you can implement in your Drupal Language Server.

## Legend

- 🟢 **Essential** - Core features every LSP should have
- 🟡 **High Value** - Very useful, implement early
- �� **Nice to Have** - Good for polish and UX
- 🟣 **Advanced** - Complex features for power users

---

## Feature List

| Priority | Feature | Request/Notification | What It Does | Drupal Use Case |
|----------|---------|---------------------|--------------|-----------------|
| 🟢 | `TEXT_DOCUMENT_DID_OPEN` | Notification | File opened | Start tracking .module files |
| 🟢 | `TEXT_DOCUMENT_DID_CHANGE` | Notification | File changed | Update parsing, re-analyze |
| 🟢 | `TEXT_DOCUMENT_DID_SAVE` | Notification | File saved | Run full validation |
| 🟢 | `TEXT_DOCUMENT_DID_CLOSE` | Notification | File closed | Clean up resources |
| 🟢 | `TEXT_DOCUMENT_COMPLETION` | Request | Autocomplete | Hooks, services, config keys |
| 🟢 | `TEXT_DOCUMENT_HOVER` | Request | Show info on hover | Hook docs, API reference |
| 🟢 | `TEXT_DOCUMENT_PUBLISH_DIAGNOSTICS` | Notification (S→C) | Send errors/warnings | Deprecated functions, syntax errors |
| 🟢 | `TEXT_DOCUMENT_DEFINITION` | Request | Go to definition | Jump to service class, hook |
| 🟡 | `TEXT_DOCUMENT_REFERENCES` | Request | Find all references | Find hook implementations |
| 🟡 | `TEXT_DOCUMENT_DOCUMENT_SYMBOL` | Request | Document outline | Show functions, hooks, classes |
| 🟡 | `TEXT_DOCUMENT_CODE_ACTION` | Request | Quick fixes | Replace deprecated APIs |
| 🟡 | `TEXT_DOCUMENT_SIGNATURE_HELP` | Request | Parameter hints | Show hook parameters as you type |
| 🟡 | `TEXT_DOCUMENT_FORMATTING` | Request | Format document | Apply Drupal coding standards |
| 🔵 | `TEXT_DOCUMENT_CODE_LENS` | Request | Inline annotations | Show "3 implementations" above hook |
| 🔵 | `TEXT_DOCUMENT_RENAME` | Request | Rename symbol | Rename service across files |
| 🔵 | `TEXT_DOCUMENT_IMPLEMENTATION` | Request | Find implementations | Find all modules implementing hook |
| 🔵 | `TEXT_DOCUMENT_INLAY_HINT` | Request | Inline hints | Show parameter names |
| 🔵 | `TEXT_DOCUMENT_FOLDING_RANGE` | Request | Code folding | Fold functions, classes |
| 🔵 | `TEXT_DOCUMENT_RANGE_FORMATTING` | Request | Format selection | Format selected code |
| 🔵 | `TEXT_DOCUMENT_DOCUMENT_HIGHLIGHT` | Request | Highlight symbol | Highlight all $variable uses |
| 🔵 | `TEXT_DOCUMENT_SELECTION_RANGE` | Request | Smart selection | Select function, then class |
| 🔵 | `TEXT_DOCUMENT_DOCUMENT_LINK` | Request | Clickable links | Make URLs in comments clickable |
| 🟣 | `TEXT_DOCUMENT_SEMANTIC_TOKENS` | Request | Semantic highlighting | Better syntax coloring |
| 🟣 | `TEXT_DOCUMENT_CALL_HIERARCHY` | Request | Call graph | Show function call tree |
| 🟣 | `TEXT_DOCUMENT_TYPE_HIERARCHY` | Request | Type inheritance | Show entity class hierarchy |
| �� | `TEXT_DOCUMENT_INLINE_COMPLETION` | Request | AI completion | Suggest code snippets |
| 🟣 | `TEXT_DOCUMENT_DECLARATION` | Request | Go to declaration | Jump to interface |
| 🟣 | `TEXT_DOCUMENT_TYPE_DEFINITION` | Request | Go to type definition | Jump to entity type class |
| 🟣 | `TEXT_DOCUMENT_ON_TYPE_FORMATTING` | Request | Format while typing | Auto-indent after `{` |
| 🟣 | `TEXT_DOCUMENT_LINKED_EDITING_RANGE` | Request | Linked editing | Edit PHP tags together |
| 🟣 | `TEXT_DOCUMENT_PREPARE_RENAME` | Request | Validate rename | Check if symbol can be renamed |
| 🟣 | `TEXT_DOCUMENT_DIAGNOSTIC` | Request | Pull diagnostics | Get diagnostics on demand |
| 🟣 | `TEXT_DOCUMENT_DOCUMENT_COLOR` | Request | Color picker | Show color preview |
| 🟣 | `TEXT_DOCUMENT_COLOR_PRESENTATION` | Request | Color formats | Convert hex to rgb |
| 🟣 | `TEXT_DOCUMENT_MONIKER` | Request | Cross-project symbols | Link to api.drupal.org |
| 🟣 | `TEXT_DOCUMENT_WILL_SAVE` | Notification | Before save | Pre-save validation |
| 🟣 | `TEXT_DOCUMENT_WILL_SAVE_WAIT_UNTIL` | Request | Before save (can edit) | Auto-format before save |
| 🟣 | `TEXT_DOCUMENT_INLINE_VALUE` | Request | Debugger values | Show values during debug |

---

## Implementation Order

### Phase 1: Foundation (Week 1)
✅ Already implemented in this project:
- TEXT_DOCUMENT_DID_OPEN
- TEXT_DOCUMENT_DID_CHANGE  
- TEXT_DOCUMENT_DID_SAVE
- TEXT_DOCUMENT_DID_CLOSE
- TEXT_DOCUMENT_COMPLETION
- TEXT_DOCUMENT_HOVER

### Phase 2: Code Quality (Week 2)
Implement next:
- TEXT_DOCUMENT_PUBLISH_DIAGNOSTICS
- TEXT_DOCUMENT_CODE_ACTION
- TEXT_DOCUMENT_DEFINITION

### Phase 3: Navigation (Week 3)
- TEXT_DOCUMENT_REFERENCES
- TEXT_DOCUMENT_DOCUMENT_SYMBOL
- TEXT_DOCUMENT_IMPLEMENTATION

### Phase 4: Productivity (Week 4)
- TEXT_DOCUMENT_SIGNATURE_HELP
- TEXT_DOCUMENT_FORMATTING
- TEXT_DOCUMENT_CODE_LENS

### Phase 5: Polish (Ongoing)
- TEXT_DOCUMENT_RENAME
- TEXT_DOCUMENT_INLAY_HINT
- TEXT_DOCUMENT_FOLDING_RANGE
- More...

---

## Quick Start for Each Feature

### Diagnostics
```python
@server.feature(TEXT_DOCUMENT_DID_CHANGE)
def validate(ls, params):
    diagnostics = []
    # Analyze code, find issues
    ls.publish_diagnostics(params.text_document.uri, diagnostics)
```

### Go to Definition
```python
@server.feature(TEXT_DOCUMENT_DEFINITION)
def definition(ls, params):
    # Find where symbol is defined
    return Location(uri="file://...", range=Range(...))
```

### Code Actions
```python
@server.feature(TEXT_DOCUMENT_CODE_ACTION)
def code_actions(ls, params):
    # Return list of quick fixes
    return [CodeAction(title="Fix...", edit=WorkspaceEdit(...))]
```

### Document Symbols
```python
@server.feature(TEXT_DOCUMENT_DOCUMENT_SYMBOL)
def symbols(ls, params):
    # Return list of functions, classes, etc.
    return [DocumentSymbol(name="hook_...", kind=SymbolKind.Function)]
```

---

## Resources

- **Full Guide**: See `05-DEVELOPMENT_GUIDE.md` for detailed explanations and examples
- **LSP Spec**: https://microsoft.github.io/language-server-protocol/
- **pygls Docs**: https://pygls.readthedocs.io/
- **Quick Start**: See `01-QUICK_START.md` for getting started

---

## Tips

1. **Start simple**: Implement basic features first
2. **Test incrementally**: Test each feature as you build it
3. **Use examples**: Copy from `05-DEVELOPMENT_GUIDE.md` examples
4. **Read the spec**: LSP spec has detailed info on each feature
5. **Debug often**: Use `server.show_message_log()` liberally
