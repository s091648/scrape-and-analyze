#!/usr/bin/env bash
# Computes a badge message/color from pytest-coverage-comment's outputs and
# writes them to $GITHUB_OUTPUT as msg/color. Shared by every job in ci.yml
# that runs pytest with the MishaKav/pytest-coverage-comment action
# (src-unit-test, backend-unit, backend-integration, src-integration-test) —
# they all feed it the same four `steps.coverage.outputs.*` values.
#
# Usage: compute-pytest-pass-rate.sh <tests> <failures> <errors> <skipped>
set -uo pipefail

TESTS="${1:-0}"
FAILURES="${2:-0}"
ERRORS="${3:-0}"
SKIPPED="${4:-0}"
PASSED=$((TESTS - FAILURES - ERRORS - SKIPPED))

if [ "$TESTS" -eq 0 ]; then
  COLOR="lightgrey"; MSG="no tests"
elif [ $((FAILURES + ERRORS)) -eq 0 ]; then
  COLOR="brightgreen"; MSG="${PASSED}/${TESTS} passed"
elif [ $((PASSED * 100 / TESTS)) -ge 90 ]; then
  COLOR="green"; MSG="${PASSED}/${TESTS} passed"
elif [ $((PASSED * 100 / TESTS)) -ge 75 ]; then
  COLOR="yellow"; MSG="${PASSED}/${TESTS} passed"
else
  COLOR="red"; MSG="${PASSED}/${TESTS} passed"
fi

echo "msg=${MSG}" >> "$GITHUB_OUTPUT"
echo "color=${COLOR}" >> "$GITHUB_OUTPUT"
