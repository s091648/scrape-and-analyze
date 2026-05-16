#!/usr/bin/env bash
# Run all test suites and print a summary. Never stops early on failure.

PASS=0
FAIL=0
RESULTS=()

run_suite() {
    local name="$1"
    shift
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  $name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if "$@"; then
        RESULTS+=("  ✅  $name")
        ((PASS++))
    else
        RESULTS+=("  ❌  $name")
        ((FAIL++))
    fi
}

run_suite "src          · unit"        make test-src
run_suite "src          · integration" make test-src-integration
run_suite "backend      · unit"        make test-backend
run_suite "backend      · integration" make test-backend-integration
run_suite "frontend     · unit"        make test-frontend
run_suite "frontend     · e2e"         make test-frontend-e2e

TOTAL=$((PASS + FAIL))

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Test Summary  ($PASS / $TOTAL passed)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
for r in "${RESULTS[@]}"; do
    echo "$r"
done
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

[ "$FAIL" -eq 0 ]
