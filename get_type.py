#!/usr/bin/env python3
"""
Script to get variable type using Phpactor CLI with line/column input.
Usage: python get_type.py <file_path> <line> <column> [--working-dir <dir>]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def line_column_to_offset(file_path: str, line: int, column: int) -> int:
    """Convert 1-based line/column to 0-based byte offset."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.splitlines()
    if line > len(lines) or line < 1:
        raise ValueError(f"Line {line} is out of range (1-{len(lines)})")

    # Calculate offset up to the target line (0-based)
    offset = 0
    for i in range(line - 1):  # line is 1-based, so line-1
        offset += len(lines[i]) + 1  # +1 for newline

    # Add column offset within the line (column is 1-based)
    if column > 0:
        target_line = lines[line - 1]
        offset += min(column - 1, len(target_line))

    return offset


def get_variable_type(file_path: str, line: int, column: int, working_dir: str = None) -> dict:
    """Get variable type using Phpactor RPC."""
    if working_dir is None:
        working_dir = str(Path(file_path).parent.parent.parent.parent.parent)

    offset = line_column_to_offset(file_path, line, column)

    # Prepare RPC request
    rpc_data = {
        "action": "offset_info",
        "parameters": {
            "source": file_path,
            "offset": offset
        }
    }

    # Run Phpactor RPC
    result = subprocess.run(
        ["phpactor", "rpc", "--working-dir", working_dir, "--pretty"],
        input=json.dumps(rpc_data),
        capture_output=True,
        text=True,
        cwd=working_dir
    )

    if result.returncode == 0:
        try:
            response = json.loads(result.stdout)
            # The information field contains JSON as a string
            if "parameters" in response and "information" in response["parameters"]:
                info_str = response["parameters"]["information"]
                info = json.loads(info_str)
                return info
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {e}")
            print(f"Raw output: {result.stdout}")
    else:
        print(f"Phpactor RPC failed: {result.stderr}")

    return {}


def main():
    parser = argparse.ArgumentParser(description="Get variable type using Phpactor CLI")
    parser.add_argument("file_path", help="Path to PHP file")
    parser.add_argument("line", type=int, help="Line number (1-based)")
    parser.add_argument("column", type=int, help="Column number (1-based)")
    parser.add_argument("--working-dir", help="Working directory (defaults to project root)")

    args = parser.parse_args()

    try:
        # Convert to absolute path if relative
        file_path = str(Path(args.file_path).resolve())

        # Get type information
        info = get_variable_type(file_path, args.line, args.column, args.working_dir)

        print(f"File: {file_path}")
        print(f"Position: {args.line}:{args.column}")
        print(f"Offset: {line_column_to_offset(file_path, args.line, args.column)}")
        print()
        print("Type Information:")
        print(json.dumps(info, indent=2))

        # Extract key fields
        if "type" in info:
            print(f"\nVariable type: {info['type']}")
        if "symbol" in info:
            print(f"Symbol: {info['symbol']}")
        if "symbol_type" in info:
            print(f"Symbol type: {info['symbol_type']}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
