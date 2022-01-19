#!/bin/bash

# Install dependencies
sudo apt update -q && sudo apt install -qy \
    build-essential \
    libelf-dev \
    wget

# Download the latest OpenCAS
git clone https://github.com/Open-CAS/open-cas-linux
pushd open-cas-linux/
git submodule update --init

# Build & Install binaries
./configure
make
sudo make install
popd

# CleanUp
rm -rf open-cas-linux/

# Verify the installation
casadm -V
