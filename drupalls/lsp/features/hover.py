"""
Hover feature - Show information when hovering over code.

For Drupal, we can show:
- Documentation for hooks
- Service descriptions
- Function signatures
- Deprecated function warnings
"""

from lsprotocol.types import (
    HoverParams,
    Hover,
    MarkupContent,
    MarkupKind,
    TEXT_DOCUMENT_HOVER,
)
from pygls.lsp.server import LanguageServer


def register_hover_handler(server: LanguageServer):
    """
    Register the hover handler.
    
    This is a REQUEST - the client expects hover content or None.
    """
    
    @server.feature(TEXT_DOCUMENT_HOVER)
    def hover(ls: LanguageServer, params: HoverParams):
        """
        Provide hover information at the cursor position.
        
        params contains:
        - text_document: The document identifier
        - position: The cursor position
        
        Returns: Hover object with markdown content or None
        """
        # Get the document
        document = ls.workspace.get_text_document(params.text_document.uri)
        
        # Get the word at the cursor position
        line = document.lines[params.position.line]
        word = get_word_at_position(line, params.position.character)
        
        if not word:
            return None
        
        # Simple example: provide info for known Drupal hooks
        drupal_hook_info = {
            "hook_form_alter": r"""
**hook_form_alter** - Perform alterations before a form is rendered

```php
function mymodule_form_alter(&$form, \Drupal\Core\Form\FormStateInterface $form_state, $form_id) {
  // Modify $form here
}
```

**Parameters:**
- `$form`: Nested array of form elements that comprise the form
- `$form_state`: The current state of the form
- `$form_id`: String representing the form's ID

**See:** https://api.drupal.org/api/drupal/core%21lib%21Drupal%21Core%21Form%21form.api.php/function/hook_form_alter
""",
            "hook_cron": """
**hook_cron** - Perform periodic actions

```php
function mymodule_hook_cron() {
  // Execute periodic tasks
}
```

Runs on every cron run. Use for maintenance tasks, cleanup, etc.

**See:** https://api.drupal.org/api/drupal/core%21core.api.php/function/hook_cron
""",
            r"\Drupal": r"""
**\Drupal** - Static Service Container Wrapper

Provides static methods to access services. 

**Common methods:**
- `\Drupal::service($id)` - Get any service
- `\Drupal::database()` - Get database connection
- `\Drupal::entityTypeManager()` - Get entity type manager
- `\Drupal::currentUser()` - Get current user
- `\Drupal::config($name)` - Get configuration

**Note:** Avoid in classes with dependency injection.
""",
        }
        
        if word in drupal_hook_info:
            return Hover(
                contents=MarkupContent(
                    kind=MarkupKind.Markdown,
                    value=drupal_hook_info[word]
                )
            )
        
        return None


def get_word_at_position(line: str, character: int) -> str:
    """
    Extract the word at the given character position.
    
    This is a simplified version - a real implementation would handle
    more complex cases like namespaces, method calls, etc.
    """
    if character >= len(line):
        return ""
    
    # Find word boundaries
    start = character
    end = character
    
    # Move start backwards to word beginning
    while start > 0 and (line[start - 1].isalnum() or line[start - 1] in '_:\\'):
        start -= 1
    
    # Move end forwards to word end
    while end < len(line) and (line[end].isalnum() or line[end] in '_:\\'):
        end += 1
    
    return line[start:end]
