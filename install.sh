#!/usr/bin/env bash
###############################################################################
# Copyright (c) ATTX Inc 2026. All Rights Reserved.
#
# Installs everything needed to BUILD custom models against an installed
# WarpTwin. The WarpTwin package itself is not installed here -- it ships as a
# signed release tarball with its own install.sh, and its dependencies
# (numpy, h5py, matplotlib, pandas, scipy, plotly, tk) come in with it.
#
# What this adds is the toolchain: a C++ compiler, cmake, SWIG and the Python
# and HDF5 development headers the wrappers compile against.
###############################################################################
set -Eeuo pipefail

log() { printf '[warptwin-custom] %s\n' "$*"; }
die() { printf '[warptwin-custom] ERROR: %s\n' "$*" >&2; exit 1; }

[[ "$(uname -s)" == "Linux" ]] || die "this script targets Ubuntu/Debian; on macOS install the toolchain with Homebrew (cmake, hdf5, swig, python3)"

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
# newer Ubuntu releases have dropped in favour of libhdf5-dev. Both provide the
# same headers, so take whichever this release has.
if ! sudo apt-get install -y libhdf5-dev; then
    sudo apt-get install -y libhdf5-serial-dev
fi

# Documentation and coverage tooling. Useful, but not worth failing over.
for pkg in doxygen graphviz asciidoctor lcov; do
    sudo apt-get install -y "${pkg}" || log "optional package '${pkg}' unavailable; skipping"
done

# WarpTwin itself has to be installed for anything here to compile or run. It is
# not on apt -- it comes from the signed release tarball -- so this only reports.
if ! dpkg -s warptwin >/dev/null 2>&1; then
    log ""
    log "WarpTwin is not installed. Custom models compile against its headers and"
    log "link against its libraries, so install the release package first:"
    log ""
    log "    tar xzf warptwin-<version>-*.tar.gz"
    log "    cd warptwin-<version>-*/ && ./install.sh"
    log ""
    exit 1
fi

log "WarpTwin $(dpkg-query -W -f='${Version}' warptwin) detected; build dependencies installed"
log "Next: mkdir build && cd build && cmake .. && make -j\$(nproc) && make test"
