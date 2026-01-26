# Functionalities to implement

## Services

 - [ ] Auto complete on services functions like `\Drupal::service('substitute_service.api')->sendApiRequest($field_subst_service_agreement, $entity->id());`
   - Do the bridge between cached services and caches classes.
   Prompt: Read all code and documentation about the services_capabilities and services_cache and write the implementation docs for implementing auto-completion for the services function. e.g., \Drupal::service('SERVICE.NAME')->functionName() or \Drupal::getContainer()->get('SERVICE.NAME')->functionName() 
   It will auto-complete the `functionName` and suggest the parameters.
   Consider that we already are caching the classes and services as defined in workspace/classes_cache.py 
   You can have access to all functions of a class using these caches.


   Create Implementation Docs for Drupal Service Method Autocompletion
Objective:
Write a new implementation document that details how to add auto-completion for methods on Drupal service objects.
Feature Requirements:
The language server should provide completion suggestions for method calls on Drupal services obtained via:
1.  \Drupal::service('a.service.name')->
2.  \Drupal::getContainer()->get('a.service.name')->
Functional Breakdown:
1.  Method Name Completion: When a user types -> after a service call, the server should suggest a list of public methods available on that service's class.
2.  Parameter Snippets: Each completion item should include a snippet for the method's parameters, like myMethod(${1:param1}, ${2:param2}).
3.  Documentation on Hover: The documentation for each method should be included in the completion item.
Technical Context & Pointers:
To build this feature, you will need to understand and use the existing workspace cache architecture.
1.  Service-to-Class Mapping: The drupalls/workspace/services_cache.py module contains the ServicesCache. This cache maps a service ID (e.g., 'a.service.name') to its corresponding PHP class (e.g., 'Drupal\mymodule\MyService').
2.  Class Member Information: The drupalls/workspace/classes_cache.py likely contains the mechanism to get methods for a given class. Your implementation plan should detail how to retrieve method information (name, parameters, documentation) for a given class name.
3.  LSP Capability Implementation: The new logic should be implemented in the existing file, drupalls/lsp/capabilities/services_capabilities.py, and integrated into the main server in drupalls/lsp/server.py.
Task:
Your primary task is to create the IMPLEMENTATION document.
Please use the @doc-writer and other relevant sub-agents to explore the codebase and produce a high-quality implementation guide.
The document should follow the standard template and include these key sections:
*   Overview: Briefly describe the feature.
*   Architecture: Explain how the new completion provider will interact with the text document, the parser (to identify the context), and the workspace caches (ServicesCache, ClassesCache).
*   Implementation Guide: Provide a detailed, step-by-step plan for developers to follow. This should include:
    *   Logic for detecting the ::service() and ->get() patterns in the source code.
    *   How to extract the service ID string from the code.
    *   How to query ServicesCache to get the class name.
    *   How to query for the class's methods.
    *   How to construct pygls.types.CompletionItem objects, ensuring you use pygls.types.InsertTextFormat.Snippet for parameters.
*   Code Examples: Provide clear, modern Python 3.9+ code examples for the key parts of the implementation.
*   Testing: Outline a strategy for testing this new capability.
