#!/usr/bin/env bash
# Appends MishaKav/pytest-coverage-comment's `summaryReport` output to the job summary.
#
# That output is a JSON-encoded string (surrounding quotes, `\n` / `\"` escapes), not raw
# markdown — echoing it as-is rendered the literal escaped text instead of the table. Decode it
# with jq first; fall back to the raw value if it ever isn't valid JSON (e.g. a future action
# version emitting plain markdown), and write nothing when the coverage step produced no output.
#
# Usage: REPORT="${{ steps.coverage.outputs.summaryReport }}" write-coverage-summary.sh
set -euo pipefail

REPORT="${REPORT:-}"
if [ -z "$REPORT" ]; then
  echo "No coverage summaryReport output — skipping job summary."
  exit 0
fi

if decoded=$(printf '%s' "$REPORT" | jq -er 'if type == "string" then . else error("not a string") end' 2>/dev/null); then
  printf '%s\n' "$decoded" >> "$GITHUB_STEP_SUMMARY"
else
  printf '%s\n' "$REPORT" >> "$GITHUB_STEP_SUMMARY"
fi
