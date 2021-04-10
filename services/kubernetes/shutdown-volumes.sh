#!/bin/bash

# Cleanup Rook configuration
sudo rm -rf /var/lib/rook
sudo dmsetup remove_all
sudo wipefs --all $volumes
