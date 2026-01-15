from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from drupalls.workspace.cache import (
    CachedDataBase,
    CachedWorkspace,
)


@dataclass
class HookDefinition(CachedDataBase):
    """Represents a Drupal hook definition."""

    hook_name: str
    signature: str
    description: str
    parameters: List[Dict[str, str]] = field(default_factory=list)
    return_type: str = "void"
    group: str = ""
    file_path: Optional[Path] = None

class HooksCache(CachedWorkspace):
    async def _scan_hooks(self):
        """
        Scan Drupal core for hook definitions.

        Hooks are documented in *.api.php files.
        """
        # Common hook definitions (hardcoded for now)
        # TODO: Parse from core/*.api.php files
        common_hooks = {
            "hook_form_alter": HookDefinition(
                hook_name="hook_form_alter",
                signature="hook_form_alter(&$form, $form_state, $form_id)",
                description="Alter forms before they are rendered",
                parameters=[
                    {
                        "name": "$form",
                        "type": "array",
                        "desc": "Nested array of form elements",
                    },
                    {
                        "name": "$form_state",
                        "type": "FormStateInterface",
                        "desc": "Current state of the form",
                    },
                    {"name": "$form_id", "type": "string", "desc": "Form ID"},
                ],
                group="Form API",
            ),
            "hook_cron": HookDefinition(
                hook_name="hook_cron",
                signature="hook_cron()",
                description="Perform periodic actions",
                group="System",
            ),
            "hook_install": HookDefinition(
                hook_name="hook_install",
                signature="hook_install()",
                description="Perform setup tasks when module is installed",
                group="Module",
            ),
            "hook_uninstall": HookDefinition(
                hook_name="hook_uninstall",
                signature="hook_uninstall()",
                description="Remove data when module is uninstalled",
                group="Module",
            ),
        }

        self._hooks.update(common_hooks)

    # ===== Public API =====

    def get_hooks(self) -> Dict[str, HookDefinition]:
        """Get all hooks."""
        return self._hooks

    def get_hook(self, hook_name: str) -> Optional[HookDefinition]:
        """Get a specific hook by name."""
        return self._hooks.get(hook_name)
