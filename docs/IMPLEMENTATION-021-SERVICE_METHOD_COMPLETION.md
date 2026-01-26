# Service Method Completion

## Overview
This document details the implementation of auto-completion for methods on Drupal service objects within the DrupalLS Language Server. This feature significantly enhances developer experience by providing intelligent suggestions for methods available on a service instance, reducing typing errors and improving code discoverability.

The completion is triggered when a user types `->` after a Drupal service call, such as:
*   `\Drupal::service('a.service.name')->`
*   `\Drupal::getContainer()->get('a.service.name')->`

The completion items will suggest public methods for the identified service, including parameter snippets and documentation where available.

## Problem/Use Case
Drupal development heavily relies on services, which are retrieved from the Dependency Injection Container. Developers frequently interact with these services by calling their methods. Without intelligent auto-completion, developers must manually recall or look up available methods and their signatures, leading to slower development, increased errors, and a steeper learning curve.

This feature addresses the need for:
1.  **Discoverability**: Easily find available methods on a service.
2.  **Accuracy**: Reduce typos and incorrect method calls.
3.  **Efficiency**: Speed up coding by providing quick access to method signatures and documentation.
4.  **Contextual Help**: Offer relevant suggestions based on the identified service.

## Architecture
The service method completion feature will be integrated into the existing plugin-based capability architecture of DrupalLS. This approach ensures modularity, extensibility, and adherence to the project's design principles.

A new capability, `ServiceMethodCompletionCapability`, will be created to handle the specific logic for detecting service calls and providing method completions. This capability will inherit from `CompletionCapability`, leveraging the base class's structure for LSP completion requests.

The `CapabilityManager` in `drupalls/lsp/capabilities/capabilities.py` will be responsible for registering and managing this new capability, ensuring it is activated and invoked when appropriate during LSP `textDocument/completion` requests.

The overall flow will involve:
1.  LSP server receives a `textDocument/completion` request.
2.  `CapabilityManager` dispatches the request to registered `CompletionCapability` instances.
3.  `ServiceMethodCompletionCapability`'s `can_handle` method determines if the current cursor position and line content match a service method completion scenario.
4.  If `can_handle` returns `True`, the `complete` method is invoked.
5.  The `complete` method extracts the service ID, queries the `WorkspaceCache` (specifically `ServicesCache` and `ClassesCache`) to retrieve service and class definitions, and then constructs `CompletionItem` objects based on the available methods.
6.  Initially, method names will be provided. Future enhancements will integrate with `PhpactorClient` to fetch richer details like parameters and documentation.

```
+---------------------+      LSP Request      +---------------------+
|       IDE/Client    | --------------------->|     DrupalLS Server |
| (e.g., VS Code)     |                       |                     |
+---------------------+                       +---------------------+
                                                        |
                                                        v
                                              +---------------------+
                                              |  LSP Message Handler|
                                              | (textDocument/completion) |
                                              +---------------------+
                                                        |
                                                        v
                                              +---------------------+
                                              |  CapabilityManager  |
                                              | (drupalls/lsp/capabilities/capabilities.py) |
                                              +---------------------+
                                                        |
                                                        v
                                              +---------------------+
                                              | ServiceMethodCompletionCapability |
                                              | (drupalls/lsp/capabilities/services_capabilities.py) |
                                              |   - Inherits from CompletionCapability |
                                              +---------------------+
                                                        |
                                                        v
                                              +---------------------+
                                              |    can_handle()     |
                                              | (Detects '->' after service call) |
                                              +---------------------+
                                                        |
                                                        v (If True)
                                              +---------------------+
                                              |     complete()      |
                                              | (Queries Caches, Builds CompletionItems) |
                                              +---------------------+
                                                        |
                                                        v
                                              +---------------------+
                                              |   WorkspaceCache    |
                                              |   (ServicesCache,   |
                                              |    ClassesCache)    |
                                              +---------------------+
                                                        |
                                                        v
                                              +---------------------+
                                              | PhpactorClient (Future) |
                                              | (For detailed method info) |
                                              +---------------------+
                                                        |
                                                        v
                                              +---------------------+
                                              | Return CompletionList |
                                              +---------------------+
```

## Implementation Guide

This section outlines the step-by-step process for implementing the `ServiceMethodCompletionCapability`.

### Step 1: Create `ServiceMethodCompletionCapability`

Use the existing file `drupalls/lsp/capabilities/services_capabilities.py` and add the following class to it. This class will inherit from `CompletionCapability` and define the basic structure for our service method completion logic.

```python
# drupalls/lsp/capabilities/services_capabilities.py

import re

from pygls.lsp.types import (
    CompletionItem,
    CompletionList,
    CompletionParams,
    InsertTextFormat,
    Position,
)

from drupalls.lsp.capabilities.capabilities import CompletionCapability
from drupalls.lsp.server import DrupalLanguageServer
from drupalls.workspace.cache import WorkspaceCache
from drupalls.workspace.classes_cache import ClassesCache
from drupalls.workspace.services_cache import ServicesCache


class ServiceMethodCompletionCapability(CompletionCapability):
    """Provides completion for methods on Drupal service objects."""

    name: str = "Service Method Completion"
    description: str = "Provides auto-completion for methods on Drupal service objects."

    def __init__(self, server: DrupalLanguageServer, workspace_cache: WorkspaceCache):
        super().__init__(server, workspace_cache)
        self.services_cache: ServicesCache = self.workspace_cache.caches["services"]
        self.classes_cache: ClassesCache = self.workspace_cache.caches["classes"]

    def can_handle(self, params: CompletionParams) -> bool:
        """
        Determines if this capability can handle the current completion request.
        Checks if the cursor is positioned after '->' on a line that contains
        a Drupal service call.
        """
        document = self.server.workspace.get_document(params.text_document.uri)
        line = document.lines[params.position.line]
        trigger_char = params.context.trigger_character if params.context else None

        # Only handle if the trigger character is '->' or if it's a direct completion request
        # and the character before the cursor is '->'
        if trigger_char == ">" or (
            trigger_char is None and line[params.position.character - 1] == ">"
        ):
            # Check if the line contains a service call pattern
            return self._extract_service_id_from_line(line, params.position) is not None
        return False

    def complete(self, params: CompletionParams) -> CompletionList | None:
        """
        Provides completion items for methods of the identified Drupal service.
        """
        document = self.server.workspace.get_document(params.text_document.uri)
        line = document.lines[params.position.line]
        service_id = self._extract_service_id_from_line(line, params.position)

        if not service_id:
            return None

        service_definition = self.services_cache.get(service_id)
        if not service_definition or not service_definition.class_name:
            self.server.lsp.show_message_log(
                f"Could not find service definition or class for service ID: {service_id}"
            )
            return None

        class_name = service_definition.class_name
        methods = self.classes_cache.get_methods(class_name)

        if not methods:
            self.server.lsp.show_message_log(
                f"No methods found for class: {class_name}"
            )
            return None

        items: list[CompletionItem] = []
        for method_name in methods:
            # For now, we only provide the method name.
            # Future enhancement will fetch parameters and documentation.
            items.append(
                CompletionItem(
                    label=method_name,
                    insert_text=f"{method_name}()",  # Simple snippet for now
                    insert_text_format=InsertTextFormat.Snippet,
                    detail=f"Method of {class_name}",
                )
            )

        return CompletionList(is_incomplete=False, items=items)

    def _extract_service_id_from_line(
        self, line: str, position: Position
    ) -> str | None:
        """
        Extracts the service ID from a line containing a Drupal service call
        up to the current cursor position.
        """
        # Adjust line to only include content up to the cursor for accurate parsing
        line_prefix = line[:position.character]

        # Regex to match common Drupal service call patterns ending with '->'
        # Pattern 1: \Drupal::service('service_id')->
        # Pattern 2: \Drupal::getContainer()->get('service_id')->
        # We need to capture the 'service_id'
        pattern = r"(?:\\Drupal::service\(|\\Drupal::getContainer\(\)->get\()['\"](?P<service_id>[a-zA-Z0-9_.-]+)['\"]\)->"
        
        match = re.search(pattern, line_prefix)
        if match:
            return match.group("service_id")
        return None
```

### Step 2: Implement the `can_handle` method

The `can_handle` method, as shown in the `ServiceMethodCompletionCapability` class above, is responsible for determining if the current completion request is relevant to service method completion.

It performs the following checks:
1.  **Trigger Character**: Verifies if the completion was triggered by `>` (part of `->`) or if it's a general completion request where the character immediately before the cursor is `>`.
2.  **Service Call Pattern**: Calls a private helper method, `_extract_service_id_from_line`, to parse the current line up to the cursor position. This helper uses a regular expression to identify common Drupal service retrieval patterns (`\Drupal::service('...')` or `\Drupal::getContainer()->get('...')`) and extract the service ID.

The `_extract_service_id_from_line` function is crucial for accurately identifying the context.

### Step 3: Implement the `complete` method

The `complete` method contains the core logic for generating completion items.

1.  **Get Current Line and Service ID**: It retrieves the current line from the document and uses `_extract_service_id_from_line` to get the service ID.
2.  **Access Caches**: It accesses the `ServicesCache` and `ClassesCache` from the `WorkspaceCache`.
3.  **Retrieve Service Definition**: It fetches the `ServiceDefinition` using the extracted `service_id`. If the service or its class name is not found, it logs a message and returns `None`.
4.  **Retrieve Class Methods**: Using the `class_name` from the `ServiceDefinition`, it queries the `ClassesCache` to get a list of public method names for that class.
5.  **Create Completion Items**: It iterates through the retrieved method names, creating a `CompletionItem` for each.
    *   Initially, `insert_text` is set to `f"{method_name}()"` with `InsertTextFormat.Snippet` to provide a basic function call snippet.
    *   `detail` provides a brief description.
6.  **Return CompletionList**: Finally, it returns a `CompletionList` containing all generated `CompletionItem`s.

### Step 4: Register the new capability

To make the `ServiceMethodCompletionCapability` active, it must be registered with the `CapabilityManager`. This involves importing the class and instantiating it within the `CapabilityManager.__init__` method, adding it to the `capabilities` dictionary.

```python
# drupalls/lsp/capabilities/capabilities.py

from typing import TYPE_CHECKING, Mapping
# ... other imports ...
from drupalls.lsp.capabilities.services_capabilities import (
    ServicesCompletionCapability,
    ServicesDefinitionCapability,
    ServicesHoverCapability,
    ServicesYamlDefinitionCapability,
    ServicesReferencesCapability,
    ServiceMethodCompletionCapability, # NEW IMPORT
)
# ... other imports ...

if TYPE_CHECKING:
    from drupalls.lsp.drupal_language_server import DrupalLanguageServer


class CapabilityManager:
    """
    Central manager for all LSP capabilities.
    """

    def __init__(
        self,
        server: "DrupalLanguageServer",
        capabilities: Mapping[str, "Capability"] | None = None,
    ):
        self.server = server

        # Default capabilities
        if capabilities is None:
            # ... other capability imports
            capabilities = {
                "services_completion": ServicesCompletionCapability(server),
                "services_hover": ServicesHoverCapability(server),
                "services_definition": ServicesDefinitionCapability(server),
                "services_yaml_definition": ServicesYamlDefinitionCapability(server),
                "services_references": ServicesReferencesCapability(server),
                "service_method_completion": ServiceMethodCompletionCapability(server), # NEW REGISTRATION
                # ... other registered capabilities
            }

        self.capabilities = dict(capabilities) if capabilities else {}
        self._registered = False
    
    # ... other methods ...
```

## Enhancing Completion with Parameters and Documentation

### Problem
The current `ClassesCache` implementation primarily focuses on storing class names and their associated methods as simple strings. It does not store detailed information such as method parameters (types, names, default values) or docblock comments. This limitation means that the initial `CompletionItem`s for service methods can only provide basic `methodName()` snippets and generic details, lacking the rich context that modern IDEs expect.

### Proposed Solution: Integration with Phpactor

To provide comprehensive method details (parameters, return types, and docblocks), we can leverage the existing `PhpactorClient` integration. Phpactor is a powerful PHP language server that can analyze PHP code and provide detailed information about classes and methods.

The `PhpactorClient` in DrupalLS can be used to query Phpactor for class details, which would include method signatures and documentation.

### Proposed Solution: Integration with Phpactor

To provide comprehensive method details (parameters, return types, and docblocks), we can leverage the existing `PhpactorClient` integration. Phpactor is a powerful PHP language server that can analyze PHP code and provide detailed information about classes and methods.

The `PhpactorClient` in DrupalLS can be used to query Phpactor for class details. The `@lsp-expert` provides the following best-practice guide for structuring the `CompletionItem`s.

#### LSP Expert Guidance on `CompletionItem` Structure

**1. `insertText` with Snippets:**

To create a parameter snippet like `myMethod(${1:param1}, ${2:param2})`, you must use `InsertTextFormat.Snippet`. This allows the IDE to create tab-stops for each parameter, making it easy for the user to fill them in.

**2. `documentation` with Markdown:**

The method's docblock should be formatted as `MarkupContent` with `MarkupKind.Markdown`. This allows for rich formatting, making the documentation highly readable. The structure should include:
*   The full method signature in a PHP code block.
*   The main description from the docblock.
*   A formatted list of `@param` tags.
*   A formatted `@return` tag.

#### Example `CompletionItem` Creation

The following helper function, based on the `@lsp-expert`'s advice, demonstrates how to build a `CompletionItem` from method details that would be returned by Phpactor.

```python
from lsprotocol.types import (
    CompletionItem,
    CompletionItemKind,
    InsertTextFormat,
    MarkupContent,
    MarkupKind,
)

def create_php_method_completion_item(
    method_name: str,
    signature: str,
    docblock: str,
    params: list[dict[str, str]] # e.g. [{'name': 'param1', 'type': 'string'}]
) -> CompletionItem:
    """
    Creates an LSP CompletionItem for a PHP method based on expert guidance.
    """
    # 1. Construct insertText with snippet
    snippet_placeholders = []
    for i, param in enumerate(params, start=1):
        snippet_placeholders.append(f"${{{i}:{param['name']}}}")

    insert_text = f"{method_name}({', '.join(snippet_placeholders)})"
    if not params:
        insert_text = f"{method_name}()"

    # 2. Construct documentation from docblock
    # In a real implementation, a dedicated docblock parser would be used.
    markdown_doc = f"```php\n{signature}\n```\n\n"
    # This is a simplified conversion for the example.
    clean_docblock = docblock.strip().replace("/**", "").replace("*/", "").strip()
    markdown_doc += "\n".join([line.strip().lstrip("* ") for line in clean_docblock.split('\n')])
    
    documentation = MarkupContent(kind=MarkupKind.Markdown, value=markdown_doc)

    # 3. Create the CompletionItem
    return CompletionItem(
        label=method_name,
        kind=CompletionItemKind.Method,
        detail=signature,
        insert_text=insert_text,
        insert_text_format=InsertTextFormat.Snippet,
        documentation=documentation,
    )
```

## Edge Cases

*   **Service Not Found**: If `services_cache.get(service_id)` returns `None`, the capability should gracefully handle this by returning an empty `CompletionList` or `None`.
*   **Class Not Found**: If the `ServiceDefinition` exists but `class_name` is missing or `classes_cache.get_methods(class_name)` returns no methods, similar graceful handling is required.
*   **Invalid Syntax**: If the line does not conform to the expected service call patterns, `_extract_service_id_from_line` should return `None`, and `can_handle` should return `False`.
*   **Multiple Service Calls on One Line**: The current regex is designed to find the last service call before the cursor. If there are multiple service calls on a single line, only the one immediately preceding the `->` will be considered. This is generally the desired behavior.
*   **Phpactor Integration Failure**: If the `PhpactorClient` call fails (e.g., Phpactor is not running, returns an error, or provides malformed data), the system should fall back to providing basic method names from `ClassesCache` to ensure some level of completion is still offered. This is handled in the enhanced `complete` method sketch.
*   **Performance with Large Classes**: Classes with a very large number of methods could potentially cause a slight delay. Caching Phpactor results would mitigate this.

## Testing

### Manual Testing
1.  **Setup**: Ensure DrupalLS is running and connected to an IDE (e.g., VS Code) with a Drupal project open.
2.  **Trigger Completion**:
    *   Open a PHP file within the Drupal project.
    *   Type `\Drupal::service('logger')->` and trigger completion (e.g., Ctrl+Space).
    *   Type `\Drupal::getContainer()->get('current_user')->` and trigger completion.
3.  **Verification**:
    *   Observe if public methods of the `LoggerChannel` or `AccountProxy` service are suggested.
    *   Check if the basic `methodName()` snippet is provided.
    *   (After Phpactor integration) Verify if parameter placeholders and documentation are displayed.

### Unit Testing
Unit tests should be created for the `ServiceMethodCompletionCapability` class, located in `tests/lsp/capabilities/test_services_capabilities.py`.

*   **Mock Dependencies**:
    *   `DrupalLanguageServer`: Mock `workspace` and `lsp` attributes.
    *   `WorkspaceCache`: Mock `caches` attribute to return mock `ServicesCache` and `ClassesCache` instances.
    *   `ServicesCache`: Mock `get` method to return `ServiceDefinition` objects.
    *   `ClassesCache`: Mock `get_methods` method to return lists of method names.
    *   `PhpactorClient`: Mock `get_class_details` method to return detailed method information (for enhanced completion testing).
*   **Test Cases**:
    *   Test `can_handle` with various valid and invalid service call patterns.
    *   Test `complete` when service is found, class is found, and methods are available.
    *   Test `complete` when service is not found.
    *   Test `complete` when class has no methods.
    *   Test `complete` with Phpactor integration, verifying correct `CompletionItem` structure (snippets, documentation).
    *   Test `complete` fallback mechanism when Phpactor integration fails.

The following unit test code should be added to `tests/lsp/capabilities/test_services_capabilities.py`:

```python
# tests/lsp/capabilities/test_services_capabilities.py

import pytest
from unittest.mock import Mock, MagicMock

from pygls.lsp.types import CompletionParams, CompletionContext, Position, TextDocumentIdentifier

from drupalls.lsp.capabilities.services_capabilities import ServiceMethodCompletionCapability
from drupalls.workspace.services_cache import ServiceDefinition

class TestServiceMethodCompletionCapability:

    @pytest.fixture
    def mock_server(self):
        server = Mock()
        server.workspace.get_document.return_value.lines = ["\\Drupal::service('test.service')->"]
        server.lsp.show_message_log = Mock()
        return server

    @pytest.fixture
    def mock_workspace_cache(self):
        cache = Mock()
        cache.caches = {
            "services": Mock(),
            "classes": Mock()
        }
        return cache

    @pytest.fixture
    def capability(self, mock_server, mock_workspace_cache):
        return ServiceMethodCompletionCapability(mock_server, mock_workspace_cache)

    def test_can_handle_with_valid_service_call_trigger_gt(self, capability):
        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri="file:///test.php"),
            position=Position(line=0, character=35),  # After ->
            context=CompletionContext(trigger_character=">")
        )
        assert capability.can_handle(params) == True

    def test_can_handle_with_valid_service_call_no_trigger(self, capability):
        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri="file:///test.php"),
            position=Position(line=0, character=35),
            context=None
        )
        assert capability.can_handle(params) == True

    def test_can_handle_with_invalid_pattern(self, capability, mock_server):
        mock_server.workspace.get_document.return_value.lines = ["$var = 'no service';"]
        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri="file:///test.php"),
            position=Position(line=0, character=20),
            context=CompletionContext(trigger_character=">")
        )
        assert capability.can_handle(params) == False

    def test_complete_with_service_and_methods(self, capability, mock_workspace_cache):
        # Mock service definition
        service_def = ServiceDefinition(
            id="test.service",
            class_name="Test\\Service\\Class",
            file_path="/path/to/service.php"
        )
        mock_workspace_cache.caches["services"].get.return_value = service_def
        mock_workspace_cache.caches["classes"].get_methods.return_value = ["method1", "method2"]

        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri="file:///test.php"),
            position=Position(line=0, character=35),
            context=CompletionContext(trigger_character=">")
        )

        result = capability.complete(params)
        assert result is not None
        assert len(result.items) == 2
        assert result.items[0].label == "method1"
        assert result.items[0].insert_text == "method1()"

    def test_complete_with_service_not_found(self, capability, mock_workspace_cache):
        mock_workspace_cache.caches["services"].get.return_value = None

        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri="file:///test.php"),
            position=Position(line=0, character=35),
            context=CompletionContext(trigger_character=">")
        )

        result = capability.complete(params)
        assert result is None

    def test_complete_with_no_methods(self, capability, mock_workspace_cache):
        service_def = ServiceDefinition(
            id="test.service",
            class_name="Test\\Service\\Class",
            file_path="/path/to/service.php"
        )
        mock_workspace_cache.caches["services"].get.return_value = service_def
        mock_workspace_cache.caches["classes"].get_methods.return_value = []

        params = CompletionParams(
            text_document=TextDocumentIdentifier(uri="file:///test.php"),
            position=Position(line=0, character=35),
            context=CompletionContext(trigger_character=">")
        )

        result = capability.complete(params)
        assert result is None

    def test_extract_service_id_from_line_service_pattern(self, capability):
        line = "\\Drupal::service('my.service.id')->"
        position = Position(line=0, character=len(line))
        result = capability._extract_service_id_from_line(line, position)
        assert result == "my.service.id"

    def test_extract_service_id_from_line_container_pattern(self, capability):
        line = "\\Drupal::getContainer()->get('another.service')->"
        position = Position(line=0, character=len(line))
        result = capability._extract_service_id_from_line(line, position)
        assert result == "another.service"

    def test_extract_service_id_from_line_double_quotes(self, capability):
        line = '\\Drupal::service("double.quoted.service")->'
        position = Position(line=0, character=len(line))
        result = capability._extract_service_id_from_line(line, position)
        assert result == "double.quoted.service"

    def test_extract_service_id_from_line_with_hyphens(self, capability):
        line = '\\Drupal::service(\'service-with-hyphens\')->'
        position = Position(line=0, character=len(line))
        result = capability._extract_service_id_from_line(line, position)
        assert result == "service-with-hyphens"

    def test_extract_service_id_from_line_no_match(self, capability):
        line = "$var = 'no service call';"
        position = Position(line=0, character=len(line))
        result = capability._extract_service_id_from_line(line, position)
        assert result is None

    def test_extract_service_id_from_line_partial_line(self, capability):
        line = "\\Drupal::service('partial.service')->more code"
        position = Position(line=0, character=40)  # Before 'more code'
        result = capability._extract_service_id_from_line(line, position)
        assert result == "partial.service"
```

## Performance Considerations

*   **Cache Utilization**: The heavy lifting of parsing service definitions and class methods is offloaded to the `ServicesCache` and `ClassesCache`. These caches are in-memory and designed for fast lookups, minimizing the performance impact of each completion request.
*   **Regex Efficiency**: The `_extract_service_id_from_line` method uses a regular expression. While generally fast, complex regexes on very long lines could be a minor bottleneck. The current regex is relatively simple and targets specific patterns, so its impact should be minimal.
*   **Phpactor Latency**: The most significant performance consideration will be the integration with `PhpactorClient`. Calls to Phpactor are network-bound (inter-process communication) and can introduce latency.
    *   **Mitigation**: Implement caching for Phpactor results within DrupalLS (e.g., a `PhpactorCache`). This would store detailed class information retrieved from Phpactor for a certain period, reducing redundant calls.
    *   **Asynchronous Calls**: Ensure that Phpactor calls are made asynchronously to avoid blocking the main LSP server thread.

## Integration

*   **Existing `CompletionCapability`**: The `ServiceMethodCompletionCapability` integrates seamlessly with the existing `CompletionCapability` base class and the `CapabilityManager`.
*   **`WorkspaceCache`**: It relies heavily on the `ServicesCache` and `ClassesCache` within the `WorkspaceCache` for its data. This ensures consistency and leverages existing data structures.
*   **`PhpactorClient`**: The enhanced version integrates with the `PhpactorClient` for richer completion details, demonstrating how DrupalLS can combine its own intelligence with external tools.
*   **LSP Server**: The capability is registered with the main `DrupalLanguageServer`, ensuring it responds to `textDocument/completion` requests.

## Future Enhancements

*   **Support for Dependency Injection**: The `@drupal-expert` highlighted that the most common and preferred way to get services is via Dependency Injection. The current implementation only handles direct static calls. Future work must include support for:
    *   **Constructor Injection**: Analyzing `__construct` method type hints to identify service properties (e.g., `$this->entityTypeManager->...`).
    *   **`create()` Method Injection**: Analyzing `$container->get()` calls within the static `create()` method of classes that implement `ContainerInjectionInterface`.
*   **Method Overload Support**: If a PHP class has methods with the same name but different signatures (though less common in PHP than some other languages), provide completion for all overloads.
*   **Context-Aware Filtering**: Filter methods based on the current context (e.g., only suggest methods that return a specific type if the return value is immediately used).
*   **Magic Methods**: Optionally provide completion for PHP magic methods (`__call`, `__get`, etc.) if they are explicitly defined or if a class implements `__call` and delegates to known methods.
*   **Go-to-Definition for Methods**: Extend this capability to provide go-to-definition for the completed methods, navigating to the PHP source file.

## References

*   [LSP Specification - Completion](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#textDocument_completion)
*   [pygls Documentation - Completion](https://pygls.readthedocs.io/en/latest/pages/completion.html)
*   [Drupal 9/10 Services](https://www.drupal.org/docs/drupal-apis/services-api/services-and-dependency-injection)
*   [Phpactor Documentation](https://phpactor.github.io/docs/index.html)
*   Existing DrupalLS `CompletionCapability` and `WorkspaceCache` implementations.

## Next Steps

1.  Implement the `ServiceMethodCompletionCapability` class in `drupalls/lsp/capabilities/services_capabilities.py`.
2.  Add the `_extract_service_id_from_line` helper method.
3.  Register the new capability in `drupalls/lsp/capabilities/capabilities.py`.
4.  Create comprehensive unit tests for the new capability, mocking necessary dependencies.
5.  (Follow-up task) Implement the `PhpactorClient` integration for richer method details, including parameter snippets and documentation. This may involve enhancing `PhpactorClient` and potentially adding a `PhpactorCache`.
6.  (Follow-up task) Enhance `ClassesCache` to store `class_file_path` for better Phpactor integration.


