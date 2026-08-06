#!/usr/bin/env bash
# Computes a badge message/color from frontend/test-results.json (vitest's
# --reporter=json output) and writes them to $GITHUB_OUTPUT as msg/color.
# Called from ci.yml's frontend-unit job — expects to run with cwd=frontend/
# (the job sets defaults.run.working-directory), same as the inline script
# it replaced.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/require-node.sh"
require_node

# See lib/vitest-pass-rate.js for what this reads and why.
read -r PASSED TOTAL < <(node "$SCRIPT_DIR/lib/vitest-pass-rate.js")
FAILED=$((TOTAL - PASSED))

if [ "$TOTAL" -eq 0 ]; then
  COLOR="lightgrey"; MSG="no tests"
elif [ "$FAILED" -eq 0 ]; then
  COLOR="brightgreen"; MSG="${PASSED}/${TOTAL} passed"
elif [ $((PASSED * 100 / TOTAL)) -ge 90 ]; then
  COLOR="green"; MSG="${PASSED}/${TOTAL} passed"
elif [ $((PASSED * 100 / TOTAL)) -ge 75 ]; then
  COLOR="yellow"; MSG="${PASSED}/${TOTAL} passed"
else
  COLOR="red"; MSG="${PASSED}/${TOTAL} passed"
fi

echo "msg=${MSG}" >> "$GITHUB_OUTPUT"
echo "color=${COLOR}" >> "$GITHUB_OUTPUT"
