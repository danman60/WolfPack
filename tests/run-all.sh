#!/bin/bash
# WolfPack Playwright Test Suite
# Usage: bash tests/run-all.sh [base_url]
# Options: SUITE=smoke|workflow|all (default: all)

BASE_URL="${1:-http://localhost:3000}"
SUITE="${SUITE:-all}"
TESTS_DIR="$(cd "$(dirname "$0")" && pwd)"
PASS=0
FAIL=0
SKIP=0
ERRORS=()

echo "=========================================="
echo "  WolfPack Test Suite (${SUITE})"
echo "  Target: $BASE_URL"
echo "=========================================="
echo ""

run_test() {
  local name="$1"
  local script="$2"
  printf "  %-40s" "[$name]"
  output=$(node "$script" "$BASE_URL" 2>&1)
  exitcode=$?
  if [ $exitcode -eq 0 ]; then
    if echo "$output" | grep -q "^SKIP"; then
      echo "SKIP"
      SKIP=$((SKIP + 1))
    else
      echo "PASS"
      PASS=$((PASS + 1))
    fi
    # Print any diagnostic lines (indented)
    echo "$output" | grep "^  " | head -5
  else
    echo "FAIL"
    ERRORS+=("  [$name] $(echo "$output" | grep -iE 'fail|error' | head -2)")
    FAIL=$((FAIL + 1))
  fi
}

# --- Smoke Tests ---
if [ "$SUITE" = "smoke" ] || [ "$SUITE" = "all" ]; then
  echo "--- Smoke Tests ---"
  run_test "Dashboard loads"           "$TESTS_DIR/01-dashboard.js"
  run_test "Navigation links"          "$TESTS_DIR/02-navigation.js"
  run_test "Intelligence page"         "$TESTS_DIR/03-intelligence.js"
  run_test "Trading page"              "$TESTS_DIR/04-trading.js"
  run_test "Portfolio page"            "$TESTS_DIR/05-portfolio.js"
  run_test "Backtest page"             "$TESTS_DIR/06-backtest.js"
  run_test "Auto-Bot page"             "$TESTS_DIR/07-autobot.js"
  run_test "LP Pools page"             "$TESTS_DIR/08-pools.js"
  run_test "Settings page"             "$TESTS_DIR/09-settings.js"
  run_test "Exchange toggle"           "$TESTS_DIR/10-exchange-toggle.js"
  run_test "Mobile responsiveness"     "$TESTS_DIR/11-mobile.js"
  run_test "API health check"          "$TESTS_DIR/12-api-health.js"
  echo ""
fi

# --- Workflow Tests ---
if [ "$SUITE" = "workflow" ] || [ "$SUITE" = "all" ]; then
  echo "--- Workflow Tests (require backend) ---"
  run_test "Paper trade submission"    "$TESTS_DIR/20-paper-trade.js"
  run_test "Intelligence cycle"        "$TESTS_DIR/21-intelligence-cycle.js"
  run_test "Approve/reject recs"       "$TESTS_DIR/22-approve-reject.js"
  run_test "Close position"            "$TESTS_DIR/23-close-position.js"
  run_test "Auto-Bot toggle/config"    "$TESTS_DIR/24-autobot-toggle.js"
  run_test "Exchange switching"        "$TESTS_DIR/25-exchange-switch.js"
  run_test "Backtest execution"        "$TESTS_DIR/26-backtest.js"
  run_test "Watchlist management"      "$TESTS_DIR/27-watchlist.js"
  echo ""
fi

echo "=========================================="
echo "  Results: $PASS passed, $FAIL failed, $SKIP skipped"
echo "=========================================="

if [ ${#ERRORS[@]} -gt 0 ]; then
  echo ""
  echo "  Failures:"
  for err in "${ERRORS[@]}"; do
    echo "$err"
  done
  echo ""
  exit 1
fi

exit 0
