#!/bin/bash

# Install dependencies
sudo yum install -y \
    elfutils-libelf-devel \
    gcc \
    "kernel-devel-uname-r = $(uname -r)" \
    kernel-devel \
    kernel-headers \
    make \
    python3 \
    rpm-build \
    wget

# Download
wget https://github.com/Open-CAS/open-cas-linux/releases/download/v20.12.2/open-cas-linux-20.12.2.0444.release.tar.gz
tar -xf open-cas-linux-20.12.2.0444.release.tar.gz
pushd open-cas-linux-20.12.2.0444.release/

# Build & Install binaries
./configure
make
sudo make install
popd

# CleanUp
rm -rf open-cas-linux-20.12.2.0444.release*

# Verify the installation
casadm -V
