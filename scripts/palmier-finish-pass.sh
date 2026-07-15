#!/bin/bash
# matrix-loop Palmier finishing pass — one headless Claude Code pass.
#
# Preconditions:
#   - Palmier Pro is OPEN (its MCP server on :19789).
#   - matrix-loop backend running on :8000.
#   - palmier-pro MCP registered at USER scope:
#       claude mcp add -s user --transport http palmier-pro http://127.0.0.1:19789/mcp
#
# Runs with a SCOPED allowlist (palmier MCP + curl only) — NOT --dangerously-skip-permissions.
# Any tool outside the allowlist is denied non-interactively, so this never runs arbitrary code.
set -euo pipefail
REPO="/Users/aa00102/matrix-loop"
export PATH="/opt/homebrew/bin:$PATH"
cd "$REPO/backend"
LOG="/tmp/palmier-finish-pass.log"
echo "=== $(date '+%F %T') palmier finish pass ===" >> "$LOG"
claude -p "$(cat "$REPO/scripts/palmier-finish-pass.md")" \
  --allowedTools "mcp__palmier-pro" "Bash(curl:*)" \
  >> "$LOG" 2>&1 || echo "pass exited non-zero (Palmier closed / nothing to do)" >> "$LOG"
echo "=== done $(date '+%T') ===" >> "$LOG"
