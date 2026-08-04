#!/usr/bin/env bash
# Commits the given files (if changed) as github-actions[bot] and pushes to
# the current branch, retrying with a rebase if the push is rejected because
# the branch moved since checkout (e.g. two bot commits racing on the same
# PR). Used by pr-automation.yml's autogen-vitepress and
# generate-release-notes jobs.
#
# Usage: git-commit-and-push.sh <commit-message> <no-changes-message> <file> [file...]
set -uo pipefail

MESSAGE="$1"
NO_CHANGES_MESSAGE="$2"
shift 2
FILES=("$@")

git config user.name  "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
git add "${FILES[@]}"

if git diff --cached --quiet; then
  echo "$NO_CHANGES_MESSAGE"
  exit 0
fi

git commit -m "$MESSAGE"
BRANCH=$(git rev-parse --abbrev-ref HEAD)
for attempt in 1 2 3 4 5; do
  if git push origin "HEAD:$BRANCH"; then
    exit 0
  fi
  echo "Push rejected (branch moved since checkout) — rebasing and retrying (attempt $attempt)"
  git fetch origin "$BRANCH"
  git rebase "origin/$BRANCH"
done

echo "::error::Failed to push commit after retries"
exit 1
