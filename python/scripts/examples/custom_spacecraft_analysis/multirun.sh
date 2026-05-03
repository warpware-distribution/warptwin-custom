#!/bin/bash
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

usage() {
    echo "Usage: $0 -f <script_file> -n <number_of_runs> [-a <additional_arguments>] [-o <output_dir>]"
}

output_dir="results"

# Parse arguments
while getopts ":f:n:a:o:" opt; do
    case $opt in
        f) script_file="$OPTARG" ;;
        n) number_of_runs="$OPTARG" ;;
        a) additional_arguments="$OPTARG" ;;
        o) output_dir="$OPTARG" ;;
        \?) echo "Invalid option: -$OPTARG" >&2; usage; exit 1 ;;
        :) echo "Option -$OPTARG requires an argument." >&2; usage; exit 1 ;;
    esac
done

# Validate inputs
if [ -z "$script_file" ] || [ -z "$number_of_runs" ]; then
    echo "Error: Both script file and number of runs are required."
    usage
    exit 1
fi

if [ ! -f "$script_file" ]; then
    echo "Error: Script file '$script_file' not found."
    exit 1
fi

if ! [[ "$number_of_runs" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: Please provide a positive integer for the number of runs."
    exit 1
fi

mkdir -p "$output_dir"
progress_file=$(mktemp)
lock_file=$(mktemp)

echo 0 > "$progress_file"

# Draw the progress bar
draw_progress_bar() {
    local completed=$1
    local total=$2
    local width=50
    local filled=$((completed * width / total))
    local empty=$((width - filled))

    # Define rainbow colors locally
    local colors=(
        "\033[31m"  # Red
        "\033[33m"  # Yellow
        "\033[32m"  # Green
        "\033[36m"  # Cyan
        "\033[34m"  # Blue
        "\033[35m"  # Magenta
    )
    local reset="\033[0m"

    local bar=""
    for ((i=0; i<filled; i++)); do
        local color_index=$((i % ${#colors[@]}))
        bar+="${colors[color_index]}#${reset}"
    done

    bar+=$(printf "%${empty}s" | tr ' ' '-')

    printf "\rProgress: [${bar}] %3d / %3d" "$completed" "$total"
}

# Parallel run function
# Parallel run function
run_single() {
    local i=$1
    local run_dir="$output_dir/run_$i/"
    mkdir -p "$run_dir"
    python3 "$script_file" ${additional_arguments} --run="$i" --out-dir="$run_dir" > "$run_dir/output.txt" 2>&1

    (
        flock -x 200
        local completed
        completed=$(< "$progress_file")
        completed=$((completed + 1))
        echo "$completed" > "$progress_file"
        draw_progress_bar "$completed" "$number_of_runs"
    ) 200>"$lock_file"
}

export -f run_single draw_progress_bar
export script_file additional_arguments output_dir number_of_runs progress_file lock_file

# Run in parallel (preferring GNU parallel, falling back to xargs)
seq 0 $((number_of_runs - 1)) | parallel -j 0 run_single 2>/dev/null || \
seq 0 $((number_of_runs - 1)) | xargs -P "$(nproc)" -I{} bash -c 'run_single "$@"' _ {}

# Final 100% and newline
draw_progress_bar "$number_of_runs" "$number_of_runs"
echo -e "\nAll Monte Carlo runs completed."

# Cleanup
rm "$progress_file" "$lock_file"