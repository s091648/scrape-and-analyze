#!/usr/bin/env bash
# Computes a badge message/color from frontend/playwright-results.xml (JUnit
# XML) and writes them to $GITHUB_OUTPUT as msg/color. Called from ci.yml's
# frontend-e2e job — expects to run with cwd=frontend/ (the job sets
# defaults.run.working-directory), same as the inline script it replaced.
set -uo pipefail

if [ -f playwright-results.xml ]; then
  TOTAL=$(grep -oP 'tests="\K[0-9]+' playwright-results.xml | head -1 || echo 0)
  FAILED=$(grep -oP 'failures="\K[0-9]+' playwright-results.xml | head -1 || echo 0)
  ERRORS=$(grep -oP 'errors="\K[0-9]+' playwright-results.xml | head -1 || echo 0)
  TOTAL=${TOTAL:-0}; FAILED=${FAILED:-0}; ERRORS=${ERRORS:-0}
  PASSED=$((TOTAL - FAILED - ERRORS))
  if [ "$TOTAL" -eq 0 ]; then
    COLOR="lightgrey"; MSG="no tests"
  elif [ $((FAILED + ERRORS)) -eq 0 ]; then
    COLOR="brightgreen"; MSG="${PASSED}/${TOTAL} passed"
  elif [ $((PASSED * 100 / TOTAL)) -ge 90 ]; then
    COLOR="green"; MSG="${PASSED}/${TOTAL} passed"
  else
    COLOR="red"; MSG="${PASSED}/${TOTAL} passed"
  fi
else
  COLOR="lightgrey"; MSG="no results"
fi

echo "msg=${MSG}" >> "$GITHUB_OUTPUT"
echo "color=${COLOR}" >> "$GITHUB_OUTPUT"
