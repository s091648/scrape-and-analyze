#!/usr/bin/env bash
# Hotfix fallback for release notes generation. PR flow already wrote the
# {{NEWEST_VERSION}} placeholder via pr-automation.yml, so this only
# generates via LLM when that placeholder is missing (i.e. a direct push to
# master skipped PR automation). Called from release.yml.
#
# Usage: generate-release-notes-fallback.sh <ref-name>
# Requires DATABASE_URL / GEMINI_API_KEY / CLAUDE_API_KEY / OPENROUTER_API_KEY
# / PYTHONPATH in the environment (forwarded to generate_release_notes.py).
set -uo pipefail

REF_NAME="$1"

if grep -q '{{NEWEST_VERSION}}' frontend/public/release-notes.json; then
  echo "Placeholder found — PR flow, skipping generation."
else
  echo "No placeholder — hotfix flow, generating via LLM."
  PREV=$(git tag --sort=-version:refname | grep -v "^${REF_NAME}$" | head -1)
  if [ -n "$PREV" ]; then
    uv run python scripts/release/generate_release_notes.py --from-tag "$PREV"
  else
    uv run python scripts/release/generate_release_notes.py
  fi
fi
