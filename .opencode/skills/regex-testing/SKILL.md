---
name: regex-testing
description: Tests and validates regular expressions against sample inputs
license: MIT
compatibility: opencode
metadata:
  audience: regex-specialist
  workflow: regex
---

## What I do

I help you test and validate regular expressions by running them against sample input strings using Python's `re` module.

## Testing Methodology

1. **Pattern Compilation**: First, attempt to compile the regex pattern to check for syntax errors
2. **Match Testing**: Test the pattern against provided sample strings
3. **Group Extraction**: If groups are present, extract and display captured groups
4. **Flags Support**: Support common regex flags (re.IGNORECASE, re.MULTILINE, re.DOTALL)

## Input Format

Provide the regex pattern and test inputs in the following format:

```
Pattern: your_regex_here
Flags: IGNORECASE,MULTILINE (optional)
Test Inputs:
- input1
- input2
- input3
```

## Output Format

For each test input, I provide:
- **Match Status**: Whether the pattern matches
- **Full Match**: The complete matched string (if any)
- **Groups**: Any captured groups (if present)
- **Position**: Start and end positions of the match

## Error Handling

- **Invalid Pattern**: Reports compilation errors with specific error messages
- **No Match**: Clearly indicates when pattern doesn't match input
- **Empty Groups**: Shows when groups are defined but don't capture anything

## Common Use Cases

- Validating email address regex patterns
- Testing URL parsing regexes
- Checking log file parsing patterns
- Validating form input patterns
- Testing code parsing regexes

## Example Usage

```
Pattern: ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$
Test Inputs:
- user@example.com
- invalid-email
- test.email+tag@domain.co.uk
```

Would return validation results for each input showing which ones match the email pattern.