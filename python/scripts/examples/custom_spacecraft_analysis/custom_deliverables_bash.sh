#!/usr/bin/env bash

#########################################################
# Bash script for running the complete budget analysis

# In one command, you can run a monte carlo analysis on your custom spacecraft class
# in a simulation for an energy budget. All data is be neatly saved and organized, then
# post processed. The final result of this script is a pdf that clearly outlines the
# simulation, dispersed values, hardware used, results, and failure points.

# NOTE: May need to run
# chmod +x ./custom_deliverables_bash.sh
# chmod +x ./multirun.sh

# Author James Tabony <james.tabony@attx.tech>
#########################################################

#* HOW TO USE
#* ./relative_path/to_this_directory/run_energy_analysis.sh <number_of_monte_carlo_runs>
#* FOR EXAMPLE, IF YOU WERE IN THE DIRECTORY: python/scripts/examples/custom_spacecraft_analysis
#* ./run_energy_analysis.sh 50

# cd into where this bash script is located
cd "$(dirname -- "$0")"

# Define arguments
NUM_MC_RUNS=$1

# Remove the results directory
rm -rf results
# Remake the results directory with mission mode paths
mkdir results
mkdir results/safe
mkdir results/nominal
mkdir results/experiment

# Remove any left-over adocs and figures
rm *.adoc
rm *.png
rm *.pdf

#########################################################
# Safe Mode Analysis
#########################################################
# Run Monte Carlo
./multirun.sh -f script.py -n $NUM_MC_RUNS -a "--case safe"

# Move Results
for d in results/run_*; do
    if [ -d "$d" ]; then
        mv "$d" results/safe
    fi
done

#########################################################
# Nominal Mode Analysis
#########################################################
# Run Monte Carlo
./multirun.sh -f script.py -n $NUM_MC_RUNS -a "--case nominal"

# Move Results
for d in results/run_*; do
    if [ -d "$d" ]; then
        mv "$d" results/nominal
    fi
done

#########################################################
# Experiment Mode Analysis
#########################################################
# Run Monte Carlo
./multirun.sh -f script.py -n $NUM_MC_RUNS -a "--case experiment"

# Move Results
for d in results/run_*; do
    if [ -d "$d" ]; then
        mv "$d" results/experiment
    fi
done

#########################################################
# Generate Document
#########################################################
python3 analysis.py
asciidoctor-pdf dexstr_energy_budget.adoc