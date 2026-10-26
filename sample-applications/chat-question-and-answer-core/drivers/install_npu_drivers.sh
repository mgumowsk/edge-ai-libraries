#!/bin/bash
#
# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Installs the Intel NPU user-space driver (level-zero loader, NPU UMD and compiler).
# The firmware is loaded by the host kernel and is not needed in the image.
# Script should be used only as a part of Dockerfiles

set -euo pipefail

NPU_DRIVER_VERSION="${NPU_DRIVER_VERSION:-1.38.0}"

case "$NPU_DRIVER_VERSION" in
"1.38.0")
    build="1.38.0.20260910-34487311128"
    sha256="1efcd4b60c22abee751d8f2705962cbcc2a569de45c7e0e670cf08afbfcdc1d2"
    ;;
*)
    echo "Error: unsupported NPU_DRIVER_VERSION '$NPU_DRIVER_VERSION'." >&2
    exit 1
    ;;
esac

echo "Installing NPU driver version: $NPU_DRIVER_VERSION"

apt-get update
apt-get install -y --no-install-recommends ca-certificates curl
mkdir /tmp/npu_deps
cd /tmp/npu_deps
curl -fsSL -o driver.tar.gz \
    "https://github.com/intel/linux-npu-driver/releases/download/v${NPU_DRIVER_VERSION}/linux-npu-driver-v${build}-ubuntu2404.tar.gz"
echo "${sha256}  driver.tar.gz" | sha256sum -c -
tar xzf driver.tar.gz
apt-get install -y --no-install-recommends libze1 libtbb12 \
    ./intel-level-zero-npu_*.deb ./intel-driver-compiler-npu_*.deb
cd /
apt-get clean
rm -rf /tmp/npu_deps /var/lib/apt/lists/*
