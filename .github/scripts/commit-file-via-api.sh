#!/usr/bin/env bash
# Commits a single file's current working-tree contents straight to a branch
# via the GitHub Contents API (not `git commit`/`git push`) — used by
# release.yml so the commit lands even though the job checked out a detached
# tag ref, not a branch. No-ops if the file has no diff.
#
# Usage: commit-file-via-api.sh <file> <repo> <branch> <commit-message>
# Requires GH_TOKEN in the environment (gh CLI auth).
set -uo pipefail

FILE="$1"
REPO="$2"
BRANCH="$3"
MESSAGE="$4"

if git diff --quiet "$FILE"; then
  echo "No changes to commit."
else
  SHA=$(gh api "/repos/$REPO/contents/$FILE" --jq '.sha')
  gh api --method PUT "/repos/$REPO/contents/$FILE" \
    --field message="$MESSAGE" \
    --field content="$(base64 -w 0 < "$FILE")" \
    --field sha="$SHA" \
    --field branch="$BRANCH"
fi
