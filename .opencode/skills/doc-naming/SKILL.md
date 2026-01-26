---
name: doc-naming
description: Determines correct filename for implementation documentation following project naming conventions
license: MIT
compatibility: opencode
metadata:
  audience: doc-writer
  workflow: documentation
---

## What I do

I help you create properly named implementation documentation files following this project's naming conventions.

## Naming Convention

All documentation files must be saved in the `docs/` folder with one of the following naming patterns:

-   **Core**: `docs/<NN>-<DESCRIPTION>.md`
-   **Appendix**: `docs/APPENDIX-<NN>-<DESCRIPTION>.md`
-   **Implementation**: `docs/IMPLEMENTATION-<NNN>-<DESCRIPTION>.md`

### Components

1.  **Prefix**: One of `IMPLEMENTATION`, `APPENDIX`, or no prefix for Core documents.
2.  **Number**:
    -   `NN`: A two-digit number for Core and Appendix documents (e.g., `01`, `02`).
    -   `NNN`: A three-digit number for Implementation documents (e.g., `001`, `002`).
3.  **Description**: A short, descriptive slug in `UPPERCASE_SNAKE_CASE`.

### Complete Examples

```
docs/01-QUICK_START.md
docs/02-WORKSPACE_CACHE_ARCHITECTURE.md
docs/APPENDIX-01-DEVELOPMENT_GUIDE.md
docs/APPENDIX-02-LSP_FEATURES_REFERENCE.md
docs/IMPLEMENTATION-001-DRUPAL_ROOT_DETECTION.md
docs/IMPLEMENTATION-002-FILE_PATH_BEST_PRACTICES.md
```

## When to use me

Use this skill whenever you need to:

-   Create a new core document
-   Create a new appendix document
-   Create a new implementation document
-   Determine the correct filename for documentation
-   Verify you're following the project's documentation naming conventions

## How to use me

1.  **List existing documents** of the desired type to find the highest existing number.

    ```bash
    # For Implementation documents
    ls docs/IMPLEMENTATION-*.md

    # For Appendix documents
    ls docs/APPENDIX-*.md

    # For Core documents
    ls docs/[0-9][0-9]-*.md
    ```

2.  **Determine the next number**. From the list of existing files, find the highest number and add 1. Pad the number with leading zeros to match the required format (`NN` or `NNN`).

3.  **Create a short, descriptive slug** for the document in `UPPERCASE_SNAKE_CASE`.

4.  **Combine the parts** to create the final filename.

## Important Notes

-   Always check the existing document count to get the correct sequence number.
-   Use `UPPERCASE_SNAKE_CASE` for the description.
-   Include the `.md` extension.
-   Never reuse documentation numbers for the same type.
-   If a doc already exists with the same number, increment to the next available number.

## Example Workflow

```bash
# 1. User wants to create a new Implementation document.
#    First, list existing implementation documents.
$ ls docs/IMPLEMENTATION-*.md
docs/IMPLEMENTATION-001-DRUPAL_ROOT_DETECTION.md
docs/IMPLEMENTATION-002-FILE_PATH_BEST_PRACTICES.md

# 2. The highest number is 2. The next number is 3.
#    Format as a three-digit number: 003.
#    Create a descriptive slug: NEW_FEATURE_GUIDE

# 3. Combine the parts to create the filename.
$ filename="docs/IMPLEMENTATION-003-NEW_FEATURE_GUIDE.md"

# 4. Create the documentation file.
$ # Now write the implementation content to this file.
```
