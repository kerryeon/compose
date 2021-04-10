#!/bin/bash

# Install dependencies
sudo apt update -q && sudo apt install -qy gcc make wget

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
