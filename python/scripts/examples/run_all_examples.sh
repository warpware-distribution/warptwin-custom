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

# GNU coreutils' `timeout` is not part of a stock macOS; Homebrew's coreutils
# installs it as `gtimeout`. Pick whichever exists and fall back to a plain
# background-process watchdog so a machine with neither still runs the suite
# rather than reporting every example as a failure.
if command -v timeout >/dev/null 2>&1; then
    run_with_timeout() { timeout --kill-after=5s "${1}s" "${@:2}"; }
elif command -v gtimeout >/dev/null 2>&1; then
    run_with_timeout() { gtimeout --kill-after=5s "${1}s" "${@:2}"; }
else
    # Exit codes match `timeout`'s: 124 when the deadline is hit, 137 when the
    # process had to be killed, so the reporting below needs no special case.
    run_with_timeout() {
        local secs="$1"; shift
        "$@" &
        local pid=$!
        local waited=0
        while kill -0 "$pid" 2>/dev/null; do
            if [ "$waited" -ge "$secs" ]; then
                kill -TERM "$pid" 2>/dev/null
                sleep 5
                if kill -0 "$pid" 2>/dev/null; then
                    kill -KILL "$pid" 2>/dev/null
                    wait "$pid" 2>/dev/null
                    return 137
                fi
                wait "$pid" 2>/dev/null
                return 124
            fi
            sleep 1
            waited=$((waited + 1))
        done
        wait "$pid"
    }
fi

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
    if run_with_timeout "$TIMEOUT_SECS" \
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