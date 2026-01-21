"""
DI refactoring code action capability.

File: drupalls/lsp/capabilities/di_code_action.py
"""
from __future__ import annotations

from lsprotocol.types import (
    CodeAction,
    CodeActionKind,
    CodeActionParams,
    WorkspaceEdit,
    TextEdit,
    Range,
    Position,
)

from drupalls.lsp.capabilities.capabilities import CodeActionCapability
from drupalls.lsp.capabilities.di_refactoring.static_call_detector import (
    StaticCallDetector,
    StaticServiceCall,
)
from drupalls.lsp.capabilities.di_refactoring.strategies.base import (
    DIRefactoringContext,
)
from drupalls.lsp.capabilities.di_refactoring.strategies.controller_strategy import (
    ControllerDIStrategy,
)
from drupalls.lsp.capabilities.di_refactoring.strategies.plugin_strategy import (
    PluginDIStrategy,
)
from drupalls.context.types import DrupalClassType


class DIRefactoringCodeActionCapability(CodeActionCapability):
    """Provides code actions to convert static Drupal calls to DI."""

    def __init__(self, server) -> None:
        super().__init__(server)
        self.static_detector = StaticCallDetector()
        self.strategies = {
            "controller": ControllerDIStrategy(),
            "form": ControllerDIStrategy(),  # Same pattern as controller
            "plugin": PluginDIStrategy(),
            "block": PluginDIStrategy(),
            "formatter": PluginDIStrategy(),
            "widget": PluginDIStrategy(),
            "queue_worker": PluginDIStrategy(),
        }

    @property
    def name(self) -> str:
        return "di_refactoring"

    @property
    def description(self) -> str:
        return "Convert static Drupal service calls to Dependency Injection"

    async def can_handle(self, params: CodeActionParams) -> bool:
        """Check if we can handle this code action request."""
        # Only handle PHP files
        uri = params.text_document.uri
        if not uri.endswith((".php", ".module", ".inc")):
            return False

        # Get document content
        doc = self.server.workspace.get_text_document(uri)
        if not doc:
            return False

        # Check if file has static Drupal calls
        static_calls = self.static_detector.detect_all(doc.source)
        
        # Return True if we found any static calls
        # The get_code_actions method will handle context gracefully
        return len(static_calls) > 0

    async def get_code_actions(
        self, params: CodeActionParams
    ) -> list[CodeAction]:
        """Return available DI refactoring actions."""
        actions: list[CodeAction] = []

        doc = self.server.workspace.get_text_document(params.text_document.uri)
        if not doc:
            return actions

        # Detect static calls
        static_calls = self.static_detector.detect_all(doc.source)
        if not static_calls:
            return actions

        # Get class context (may be None if type_checker unavailable)
        context = None
        if self.server.type_checker:
            context = await self.server.type_checker.get_class_context(
                params.text_document.uri, params.range.start
            )

        # Determine class type and line (fallback to regex detection)
        class_type, class_line = self._get_class_info(doc.source, context)
        
        # Get unique services
        unique_services = self.static_detector.get_unique_services(static_calls)
        service_ids = list(unique_services.keys())

        # Create action for converting all static calls
        actions.append(
            CodeAction(
                title=f"Convert {len(static_calls)} static calls to Dependency Injection",
                kind=CodeActionKind.RefactorRewrite,
                data={
                    "type": "convert_all_to_di",
                    "uri": params.text_document.uri,
                    "service_ids": service_ids,
                    "class_type": class_type,
                    "class_line": class_line,
                },
            )
        )

        # Create action for single service at cursor
        cursor_call = self._find_call_at_cursor(
            static_calls, params.range.start.line
        )
        if cursor_call:
            actions.append(
                CodeAction(
                    title=f"Inject '{cursor_call.service_id}' service",
                    kind=CodeActionKind.RefactorRewrite,
                    data={
                        "type": "inject_single_service",
                        "uri": params.text_document.uri,
                        "service_id": cursor_call.service_id,
                        "class_type": class_type,
                        "class_line": class_line,
                    },
                )
            )

        return actions
    
    def _get_class_info(
        self, content: str, context
    ) -> tuple[str, int]:
        """
        Get class type and line from context or fallback to regex detection.
        
        Returns:
            Tuple of (class_type, class_line)
        """
        import re
        
        # If we have context, use it
        if context and context.drupal_type != DrupalClassType.UNKNOWN:
            return context.drupal_type.value, context.class_line
        
        # Fallback: detect class type from content using regex
        lines = content.split("\n")
        class_line = 0
        class_type = "controller"  # Default
        
        # Find class declaration
        class_pattern = re.compile(
            r"^\s*(final\s+|abstract\s+)?(class)\s+(\w+)"
            r"(\s+extends\s+(\w+))?"
            r"(\s+implements\s+[\w,\s\\]+)?"
        )
        
        for i, line in enumerate(lines):
            match = class_pattern.search(line)
            if match:
                class_line = i
                parent_class = match.group(5) or ""
                implements = match.group(6) or ""
                
                # Determine type from parent class
                parent_lower = parent_class.lower()
                if "controllerbase" in parent_lower:
                    class_type = "controller"
                elif "formbase" in parent_lower or "configformbase" in parent_lower:
                    class_type = "form"
                elif "blockbase" in parent_lower:
                    class_type = "block"
                elif "pluginbase" in parent_lower:
                    class_type = "plugin"
                elif "formatterbase" in parent_lower:
                    class_type = "formatter"
                elif "widgetbase" in parent_lower:
                    class_type = "widget"
                elif "queueworkerbase" in parent_lower:
                    class_type = "queue_worker"
                # Check interfaces
                elif "forminterface" in implements.lower():
                    class_type = "form"
                elif "containerinjectioninterface" in implements.lower():
                    class_type = "controller"  # Uses controller pattern
                
                break
        
        return class_type, class_line

    def _find_call_at_cursor(
        self, calls: list[StaticServiceCall], line: int
    ) -> StaticServiceCall | None:
        """Find the static call at the cursor line."""
        for call in calls:
            if call.line_number == line:
                return call
        return None

    async def resolve(self, action: CodeAction) -> CodeAction:
        """Resolve a code action with full edit details."""
        if not action.data:
            return action

        data = action.data
        action_type = data.get("type")

        if action_type == "convert_all_to_di":
            action.edit = await self._resolve_convert_all(data)
        elif action_type == "inject_single_service":
            action.edit = await self._resolve_inject_single(data)

        return action

    async def _resolve_convert_all(self, data: dict) -> WorkspaceEdit:
        """Resolve full DI conversion."""
        uri = data["uri"]
        service_ids = data["service_ids"]
        class_type = data["class_type"]
        class_line = data.get("class_line", 0)

        doc = self.server.workspace.get_text_document(uri)
        if not doc:
            return WorkspaceEdit()

        # Select strategy
        strategy = self.strategies.get(class_type)
        if not strategy:
            return WorkspaceEdit()

        # Create refactoring context
        refactor_context = DIRefactoringContext(
            file_uri=uri,
            file_content=doc.source,
            class_line=class_line,
            drupal_type=class_type,
            services_to_inject=service_ids,
        )

        # Generate edits
        refactoring_edits = strategy.generate_edits(refactor_context)

        # Also replace static calls with property access
        static_calls = self.static_detector.detect_all(doc.source)
        replacement_edits = self._generate_replacement_edits(
            static_calls, service_ids
        )

        # Combine all edits
        all_text_edits = [e.text_edit for e in refactoring_edits]
        all_text_edits.extend(replacement_edits)

        # Sort by position (reverse order for safe application)
        all_text_edits.sort(
            key=lambda e: (e.range.start.line, e.range.start.character),
            reverse=True,
        )

        return WorkspaceEdit(changes={uri: all_text_edits})

    async def _resolve_inject_single(self, data: dict) -> WorkspaceEdit:
        """Resolve single service injection."""
        # Similar to convert_all but with single service
        return await self._resolve_convert_all({
            **data,
            "service_ids": [data["service_id"]],
        })

    def _generate_replacement_edits(
        self,
        calls: list[StaticServiceCall],
        service_ids: list[str],
    ) -> list[TextEdit]:
        """Generate edits to replace static calls with property access."""
        from drupalls.lsp.capabilities.di_refactoring.service_interfaces import (
            get_property_name,
        )

        edits = []
        for call in calls:
            if call.service_id in service_ids:
                prop_name = get_property_name(call.service_id)
                edits.append(
                    TextEdit(
                        range=Range(
                            start=Position(
                                line=call.line_number,
                                character=call.column_start,
                            ),
                            end=Position(
                                line=call.line_number,
                                character=call.column_end,
                            ),
                        ),
                        new_text=f"$this->{prop_name}",
                    )
                )
        return edits
