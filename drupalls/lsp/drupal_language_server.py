from pygls.lsp.server import LanguageServer

from drupalls.lsp.capabilities.capabilities import CapabilityManager
from drupalls.workspace.cache import WorkspaceCache


class DrupalLanguageServer(LanguageServer):
    """
    Custom Language Server with Drupal-specific attributes.

    Attributes:
        workspace_cache: Cache for parsed Drupal data (services, hooks, etc.)
    """

    def __init__(self, name: str, version: str):
        super().__init__(name, version)

        self.workspace_cache: WorkspaceCache | None = None
        self.capability_manager: CapabilityManager | None 
