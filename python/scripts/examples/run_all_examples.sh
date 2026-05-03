#!/bin/bash
# run_all.sh - Run script.py in each subdirectory, suppress output, report failures

declare -a FAILURES
declare -a FAILURE_LOGS
TOTAL=0
PASSED=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

BASE_DIR="$(pwd)"

# Use a non-interactive matplotlib backend so plt.show() doesn't block
export MPLBACKEND=Agg
export PYTHONUNBUFFERED=1

TIMEOUT_SECS=120

for dir in */; do
    dir="${dir%/}"
    cd "$BASE_DIR/$dir" || continue

    if [ ! -f "script.py" ]; then
        echo -e "${YELLOW}[SKIP]${NC} No script.py in $dir"
        cd "$BASE_DIR" || exit 1
        continue
    fi

    TOTAL=$((TOTAL + 1))
    printf "[%2d] %-60s " "$TOTAL" "$dir/script.py"

    LOG=$(mktemp)
    if timeout --kill-after=5s "${TIMEOUT_SECS}s" \
           python3 script.py --end=10 >"$LOG" 2>&1; then
        echo -e "${GREEN}[PASS]${NC}"
        PASSED=$((PASSED + 1))
        rm -f "$LOG"
    else
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
            REASON="TIMEOUT after ${TIMEOUT_SECS}s"
        elif [ $EXIT_CODE -eq 137 ]; then
            REASON="KILLED (timeout, didn't respond to SIGTERM)"
        else
            REASON="exit $EXIT_CODE"
        fi
        echo -e "${RED}[FAIL]${NC} ($REASON)"
        FAILURES+=("$dir/script.py — $REASON")
        FAILURE_LOGS+=("$LOG")
    fi

    cd "$BASE_DIR" || exit 1
done

# Summary
echo ""
echo "========================================"
echo -e "${BOLD}SUMMARY${NC}"
echo "========================================"
echo "Total runs:  $TOTAL"
echo -e "${GREEN}Passed:      $PASSED${NC}"
echo -e "${RED}Failed:      ${#FAILURES[@]}${NC}"

if [ ${#FAILURES[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}${BOLD}FAILED SCRIPTS:${NC}"
    for i in "${!FAILURES[@]}"; do
        echo -e "  ${RED}✗${NC} ${FAILURES[$i]}"
        echo -e "    ${YELLOW}last 15 lines of output:${NC}"
        tail -n 15 "${FAILURE_LOGS[$i]}" | sed 's/^/      /'
        rm -f "${FAILURE_LOGS[$i]}"
        echo ""
    done
    exit 1
fi

echo -e "\n${GREEN}${BOLD}All scripts passed!${NC}"
exit 0