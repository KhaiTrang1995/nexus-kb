#!/bin/bash
# validate-bash.sh – Pre-tool-use hook
# Blocks unsafe shell operations before execution.

set -euo pipefail

COMMAND="${1:-}"

# ── Blocked patterns ────────────────────────────────────────────────────────
BLOCKED_PATTERNS=(
  "rm -rf /"
  "rm -rf ~"
  "mkfs"
  "dd if="
  ":(){ :|:& };:"   # fork bomb
  "> /dev/sda"
  "chmod -R 777 /"
  "curl.*| bash"
  "wget.*| bash"
  "eval \"\$(curl"
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qiF "$pattern"; then
    echo "BLOCKED: Unsafe command detected: $pattern" >&2
    exit 1
  fi
done

# ── Warn on destructive but allowed operations ──────────────────────────────
WARN_PATTERNS=(
  "git push --force"
  "git reset --hard"
  "DROP TABLE"
  "DELETE FROM"
  "truncate"
)

for pattern in "${WARN_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qiF "$pattern"; then
    echo "WARNING: Potentially destructive command: $pattern" >&2
    echo "Proceed only if you have confirmed this is intentional." >&2
  fi
done

echo "Command validated."
exit 0
