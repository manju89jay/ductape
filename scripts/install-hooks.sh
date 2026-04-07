#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
SCRIPT="$REPO_ROOT/scripts/pre-push.sh"

# Resolve hooks dir — handles both regular repos and worktrees
if [ -f "$REPO_ROOT/.git" ]; then
  # Worktree: .git is a file with "gitdir: <path>"
  HOOK_DIR="$(sed 's/gitdir: //' "$REPO_ROOT/.git")/hooks"
else
  HOOK_DIR="$REPO_ROOT/.git/hooks"
fi

mkdir -p "$HOOK_DIR"
ln -sf "$SCRIPT" "$HOOK_DIR/pre-push"
chmod +x "$SCRIPT"
echo "Installed pre-push hook -> $HOOK_DIR/pre-push"
