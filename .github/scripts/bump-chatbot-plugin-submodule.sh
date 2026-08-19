#!/usr/bin/env bash
# Fetches chatbot-plugin's tags and, if its latest v* tag isn't already what
# the chatbot-plugin/ submodule has checked out, checks that tag's commit out
# there. Does NOT commit — the caller commits the resulting gitlink change
# (see git-commit-and-push.sh) since the two callers below commit it
# differently (a plain push vs. one that also needs [skip ci]).
#
# Sets GITHUB_OUTPUT `changed` (true/false) and, when changed, `latest_tag`.
#
# Used by:
#   - bump-chatbot-plugin-submodule.yml (daily cron) — keeps the pointer from
#     drifting stale between scrape-analyzer releases, since chatbot-plugin's
#     own release.yml appends a version-bump commit (and force-moves the tag
#     to it) after every tag push there.
#   - release.yml — deploy-production.sh only deploys chatbot-plugin from a
#     submodule commit that's already tagged in chatbot-plugin's own repo
#     (see that script's own comment); relying solely on the daily cron
#     having already caught up before a given scrape-analyzer release would
#     silently skip chatbot-plugin's production deploy whenever the two
#     happen to race. Running this here too makes every scrape-analyzer
#     release self-healing instead of depending on cron timing.
set -euo pipefail

cd chatbot-plugin
git fetch --tags origin -q
LATEST_TAG=$(git tag --list 'v*' --sort=-v:refname | head -1)
if [ -z "$LATEST_TAG" ]; then
  echo "No v* tags found in chatbot-plugin — nothing to do."
  echo "changed=false" >> "$GITHUB_OUTPUT"
  exit 0
fi

CURRENT=$(git rev-parse HEAD)
TARGET=$(git rev-parse "$LATEST_TAG^{commit}")
if [ "$CURRENT" = "$TARGET" ]; then
  echo "Already pinned to $LATEST_TAG ($CURRENT) — nothing to do."
  echo "changed=false" >> "$GITHUB_OUTPUT"
  exit 0
fi

git checkout "$LATEST_TAG"
echo "latest_tag=$LATEST_TAG" >> "$GITHUB_OUTPUT"
echo "changed=true" >> "$GITHUB_OUTPUT"
