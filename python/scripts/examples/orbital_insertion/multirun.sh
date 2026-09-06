#!/usr/bin/env bash
###############################################################################
# Copyright (c) ATTX INC 2026. All Rights Reserved.
#
# This software and associated documentation (the "Software") are the
# proprietary and confidential information of ATTX, INC. The Software is
# furnished under a license agreement between ATTX and the user organization
# and may be used or copied only in accordance with the terms of the agreement.
# Refer to 'license/attx_license.adoc' for standard license terms.
#
# EXPORT CONTROL NOTICE: THIS SOFTWARE MAY INCLUDE CONTENT CONTROLLED UNDER THE
# INTERNATIONAL TRAFFIC IN ARMS REGULATIONS (ITAR) OR THE EXPORT ADMINISTRATION
# REGULATIONS (EAR99). No part of the Software may be used, reproduced, or
# transmitted in any form or by any means, for any purpose, without the express
# written permission of ATTX, INC.
###############################################################################
set -euo pipefail

usage() {
    echo "Usage: $0 -f <script_file> -n <number_of_runs> [-a <additional_arguments>] [-o <output_dir>] [-j <parallel_jobs>]"
    echo ""
    echo "  -f  Path to the Python simulation script (required, must be absolute or resolvable)"
    echo "  -n  Number of Monte Carlo runs (required, positive integer)"
    echo "  -a  Additional arguments passed verbatim to each run"
    echo "  -o  Output directory (default: results)"
    echo "  -j  Max parallel jobs (default: number of CPU cores)"
}

# ── Defaults ──────────────────────────────────────────────────────────────────
output_dir="results"
additional_arguments=""
max_jobs="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)"

# ── Argument parsing ──────────────────────────────────────────────────────────
while getopts ":f:n:a:o:j:h" opt; do
    case $opt in
        f) script_file="$OPTARG" ;;
        n) number_of_runs="$OPTARG" ;;
        a) additional_arguments="$OPTARG" ;;
        o) output_dir="$OPTARG" ;;
        j) max_jobs="$OPTARG" ;;
        h) usage; exit 0 ;;
        \?) echo "Error: Invalid option -$OPTARG" >&2; usage; exit 1 ;;
        :)  echo "Error: Option -$OPTARG requires an argument." >&2; usage; exit 1 ;;
    esac
done

# ── Input validation ──────────────────────────────────────────────────────────
if [ -z "${script_file:-}" ] || [ -z "${number_of_runs:-}" ]; then
    echo "Error: Both -f <script_file> and -n <number_of_runs> are required." >&2
    usage; exit 1
fi

# Resolve to absolute path so subshells always find the script
script_file="$(cd "$(dirname "$script_file")" && pwd)/$(basename "$script_file")"

if [ ! -f "$script_file" ]; then
    echo "Error: Script file '$script_file' not found." >&2
    exit 1
fi

if ! [[ "$number_of_runs" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: -n must be a positive integer (got: '$number_of_runs')." >&2
    exit 1
fi

if ! [[ "$max_jobs" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: -j must be a positive integer (got: '$max_jobs')." >&2
    exit 1
fi

mkdir -p "$output_dir"

# ── Temp files ────────────────────────────────────────────────────────────────
progress_file="$(mktemp)"
lock_file="$(mktemp)"
failed_file="$(mktemp)"   # newline-separated list of failed run indices

# ── Progress-counter lock ─────────────────────────────────────────────────────
# `flock` comes from util-linux and is not present on macOS, so guard the shared
# counter with an atomic `mkdir` when it is missing: mkdir either creates the
# directory or fails, on every POSIX filesystem, which is all the mutual
# exclusion a counter increment needs.
lock_dir="${lock_file}.d"
if command -v flock >/dev/null 2>&1; then
    lock_acquire() { exec 200>"$lock_file"; flock -x 200; }
    lock_release() { exec 200>&-; }
else
    lock_acquire() { until mkdir "$lock_dir" 2>/dev/null; do sleep 0.05; done; }
    lock_release() { rmdir "$lock_dir" 2>/dev/null || true; }
fi

echo 0 > "$progress_file"

cleanup() {
    rm -f "$progress_file" "$lock_file" "$failed_file"
}
trap cleanup EXIT

# ── Progress bar ──────────────────────────────────────────────────────────────
draw_progress_bar() {
    local completed=$1
    local total=$2
    local failed_count=$3
    local width=50
    local filled=$(( completed * width / total ))
    local empty=$(( width - filled ))

    local colors=(
        "\033[31m" "\033[33m" "\033[32m"
        "\033[36m" "\033[34m" "\033[35m"
    )
    local reset="\033[0m"

    local bar=""
    for (( i = 0; i < filled; i++ )); do
        bar+="${colors[$(( i % ${#colors[@]} ))]}#${reset}"
    done
    bar+="$(printf "%${empty}s" | tr ' ' '-')"

    local fail_note=""
    if [ "$failed_count" -gt 0 ]; then
        fail_note="  \033[31m${failed_count} failed\033[0m"
    fi

    printf "\rProgress: [${bar}] %3d / %3d${fail_note}" \
           "$completed" "$total"
}

# ── Per-run worker ────────────────────────────────────────────────────────────
run_single() {
    local i=$1
    local run_dir="${output_dir}/run_${i}"
    mkdir -p "$run_dir"

    # Run the simulation; capture exit code without aborting the script
    set +e
    python3 "$script_file" \
        ${additional_arguments} \
        --run="$i" \
        --out-dir="$run_dir" \
        > "$run_dir/output.txt" 2>&1
    local exit_code=$?
    set -e

    lock_acquire

    # Record failure
    if [ "$exit_code" -ne 0 ]; then
        echo "$i" >> "$failed_file"
    fi

    local completed
    completed=$(< "$progress_file")
    completed=$(( completed + 1 ))
    echo "$completed" > "$progress_file"

    local failed_count
    failed_count=$(wc -l < "$failed_file")

    draw_progress_bar "$completed" "$number_of_runs" "$failed_count"

    lock_release

    return $exit_code
}

export -f run_single draw_progress_bar lock_acquire lock_release
export script_file additional_arguments output_dir number_of_runs
export progress_file lock_file lock_dir failed_file

# ── Parallel execution ────────────────────────────────────────────────────────
# Use GNU parallel if available (better job control); fall back to xargs.
# 'set +e' so a non-zero exit from individual runs doesn't abort the script —
# we collect failures ourselves and report at the end.
echo "Starting $number_of_runs runs with up to $max_jobs parallel jobs..."
echo "Script:  $script_file"
echo "Output:  $output_dir"
echo ""

set +e
if command -v parallel >/dev/null 2>&1; then
    seq 0 $(( number_of_runs - 1 )) \
        | parallel --halt never -j "$max_jobs" run_single {}
else
    seq 0 $(( number_of_runs - 1 )) \
        | xargs -P "$max_jobs" -I{} bash -c 'run_single "$@"' _ {}
fi
set -e

# Ensure progress bar shows 100% with final failed count
failed_count=$(wc -l < "$failed_file" | tr -d ' ')
draw_progress_bar "$number_of_runs" "$number_of_runs" "$failed_count"
printf "\n"

# ── Summary ───────────────────────────────────────────────────────────────────
passed=$(( number_of_runs - failed_count ))
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Monte Carlo complete: $passed / $number_of_runs runs succeeded"

if [ "$failed_count" -gt 0 ]; then
    echo ""
    echo "  ⚠  $failed_count run(s) exited with errors:"
    # Sort numerically and print each with its output file path
    sort -n "$failed_file" | while read -r idx; do
        local_log="${output_dir}/run_${idx}/output.txt"
        printf "     run_%-4s  →  %s\n" "$idx" "$local_log"
        # Print the last non-empty line of the log as a one-line hint
        last_line=$(grep -v '^\s*$' "$local_log" 2>/dev/null | tail -1)
        if [ -n "$last_line" ]; then
            printf "               last line: %s\n" "$last_line"
        fi
    done
    echo ""
    echo "  Full output for each failed run is in its output.txt."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit 1   # Signal to generate_report.sh that some runs failed
else
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
fi