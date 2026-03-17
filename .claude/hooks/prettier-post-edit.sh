#!/usr/bin/env bash
# Post-edit hook: auto-format UI source files with prettier
# Reads tool_input JSON from stdin, extracts file_path, runs prettier if it matches ui/src/**

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.file // empty')

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Only format UI source files
if [[ "$FILE_PATH" == */ui/src/*.ts ]] || [[ "$FILE_PATH" == */ui/src/*.tsx ]] || [[ "$FILE_PATH" == */ui/src/*.css ]]; then
  cd "$(dirname "$0")/../../ui"
  bunx prettier --write "$FILE_PATH" > /dev/null 2>&1
fi
