#!/bin/sh
# Blocks force-pushes so history rewrites always go through a human.
# Claude Code PreToolUse hook for Bash: the tool call arrives as JSON on stdin;
# exit code 2 blocks the command and shows the message to the model.
# Known false positive: a command whose text merely mentions a forced push
# (say, writing a doc with a heredoc) is blocked too. Use the Write tool for that.
input=$(cat)
if command -v jq >/dev/null 2>&1; then
  cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)
else
  cmd=$input
fi
if printf '%s' "$cmd" | grep -qE 'git[[:space:]]+push[^|;&]*([[:space:]]-f([[:space:]]|$|")|--force|[[:space:]]\+[A-Za-z0-9_/.-]+)'; then
  echo "Blocked: force-push rewrites shared history. A human runs this one." >&2
  exit 2
fi
exit 0
