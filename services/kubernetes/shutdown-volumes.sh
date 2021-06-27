#!/bin/bash

# Cleanup Rook configuration
sudo dmsetup remove_all
sudo rm -rf /dev/ceph-*
sudo rm -rf /dev/mapper/ceph--*
sudo rm -rf /var/lib/rook/
sudo rm -rf /var/lib/kubelet/plugins/
sudo rm -rf /var/lib/kubelet/plugins_registry/

# Cleanup LVMs
for volume in $volumes; do
    sudo wipefs --all $volume && sync
    sudo sgdisk --zap-all $volume && sync
    sudo dd if=/dev/zero of=$volume bs=1M count=100 conv=direct,dsync && sync
    sudo blkdiscard $volume && sync
    sudo partprobe $volume && sync
done
