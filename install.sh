#!/usr/bin/env bash
###############################################################################
# Copyright (c) ATTX Inc 2026. All Rights Reserved.
#
# This software and associated documentation (the "Software") are the
# proprietary and confidential information of ATTX INC. The Software is
# furnished under a license agreement between ATTX and the user organization
# and may be used or copied only in accordance with the terms of the agreement.
# Refer to 'license/attx_license.adoc' for standard license terms.
#
# EXPORT CONTROL NOTICE: THIS SOFTWARE MAY INCLUDE CONTENT CONTROLLED UNDER THE
# INTERNATIONAL TRAFFIC IN ARMS REGULATIONS (ITAR) OR THE EXPORT ADMINISTRATION
# REGULATIONS (EAR99). No part of the Software may be used, reproduced, or
# transmitted in any form or by any means, for any purpose, without the express
# written permission of ATTX INC.
###############################################################################
#
# Installs everything needed to BUILD custom models against an installed
# WarpTwin, on Ubuntu/Debian or macOS. The WarpTwin package itself is not
# installed here -- it ships as a signed release with its own installer, and its
# dependencies (numpy, h5py, matplotlib, pandas, scipy, plotly, tk) come in with
# it.
#
# What this adds is the toolchain: a C++ compiler, cmake, SWIG and the Python
# and HDF5 development headers the wrappers compile against.
###############################################################################
set -Eeuo pipefail

log() { printf '[warptwin-custom] %s\n' "$*"; }
die() { printf '[warptwin-custom] ERROR: %s\n' "$*" >&2; exit 1; }

###############################################################################
# Ubuntu / Debian
###############################################################################
install_linux() {
    command -v apt-get >/dev/null 2>&1 \
        || die "this script supports Ubuntu/Debian (apt-get) and macOS (Homebrew); neither found"

    sudo apt-get update -y

    # Hard requirements. Without any one of these the build cannot proceed.
    sudo apt-get install -y \
        build-essential \
        cmake \
        git \
        pkg-config \
        python3 \
        python3-dev \
        python3-tk \
        swig

    # libhdf5-serial-dev is the historical name and a transitional package that
    # newer Ubuntu releases have dropped in favour of libhdf5-dev. Both provide
    # the same headers, so take whichever this release has.
    if ! sudo apt-get install -y libhdf5-dev; then
        sudo apt-get install -y libhdf5-serial-dev
    fi

    # Documentation and coverage tooling. Useful, but not worth failing over.
    for pkg in doxygen graphviz asciidoctor lcov; do
        sudo apt-get install -y "${pkg}" || log "optional package '${pkg}' unavailable; skipping"
    done
}

###############################################################################
# macOS
#
# The Command Line Tools supply clang and make; everything else comes from
# Homebrew. Note that the compiler is a hard prerequisite rather than something
# this script can install unattended -- `xcode-select --install` opens a GUI
# dialog -- so it is checked for and reported instead.
###############################################################################
install_macos() {
    xcode-select -p >/dev/null 2>&1 \
        || die "the Xcode Command Line Tools are not installed. Run 'xcode-select --install', let it finish, then re-run this script."

    command -v brew >/dev/null 2>&1 \
        || die "Homebrew is not installed. Install it from https://brew.sh and re-run this script."

    # Hard requirements.
    #
    # hdf5 is needed for its headers alone: HighFive pulls them in through
    # Hdf5Logger.h, so a model cannot compile without them. WarpTwin ships the
    # HDF5 *library* it runs against inside its own prefix, and nothing built
    # here links Homebrew's.
    #
    # python-tk is what the matplotlib windows in the example scripts draw into.
    brew install cmake swig hdf5 python-tk || die "brew install of the required packages failed"

    # Documentation and coverage tooling. Useful, but not worth failing over.
    for pkg in doxygen graphviz asciidoctor lcov; do
        brew install "${pkg}" || log "optional package '${pkg}' unavailable; skipping"
    done

    # GNU coreutils is genuinely optional: the example runner and the Monte
    # Carlo drivers fall back to portable equivalents when `timeout`, `nproc`
    # and `flock` are missing. It just makes them behave exactly as on Ubuntu.
    brew install coreutils || log "optional package 'coreutils' unavailable; skipping"
}

###############################################################################
# Confirm WarpTwin itself is present
#
# Custom models compile against its headers and link against its libraries, so
# there is nothing to build without it. It is not on apt or in Homebrew -- it
# comes from the signed release -- so this only reports.
###############################################################################
require_warptwin() {
    local prefix
    for prefix in "${WARPTWIN_ROOT:-}" /usr /usr/local/warptwin /usr/local /opt/warptwin; do
        [[ -n "${prefix}" ]] || continue
        if [[ -f "${prefix}/include/warptwin/simulation/Model.h" ]]; then
            log "WarpTwin found at ${prefix}"
            return 0
        fi
    done

    log ""
    log "WarpTwin is not installed. Custom models compile against its headers and"
    log "link against its libraries, so install the release package first, then"
    log "confirm it with 'warptwin-doctor'."
    log ""
    return 1
}

###############################################################################
# Main
###############################################################################
case "$(uname -s)" in
    Linux)  install_linux ;;
    Darwin) install_macos ;;
    *)      die "unsupported platform '$(uname -s)'; this script supports Linux (Ubuntu/Debian) and macOS" ;;
esac

require_warptwin || exit 1

if [[ "$(uname -s)" == "Darwin" ]]; then
    jobs_flag='-j$(sysctl -n hw.ncpu)'
else
    jobs_flag='-j$(nproc)'
fi
log "build dependencies installed"
log "Next: mkdir build && cd build && cmake .. && make ${jobs_flag} && make test"
