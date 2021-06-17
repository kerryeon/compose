#!/bin/bash

# Cleanup Rook configuration
sudo rm -rf /dev/ceph-*
sudo rm -rf /dev/mapper/ceph--*
sudo rm -rf /var/lib/rook
sudo dmsetup remove_all
sudo wipefs --all $volumes

# Cleanup LVMs
for volume in $volumes; do
    sudo dd if=/dev/zero of=$volume bs=512 count=4096 conv=notrunc
done
