#!/bin/bash

# Cleanup LVMs
for volume in $volumes; do
    sudo sgdisk --zap-all $volume && sync
    sudo dd if=/dev/zero of=$volume bs=1M count=100 conv=direct,dsync && sync
    sudo blkdiscard $volume && sync
    sudo partprobe $volume && sync
done

# Cleanup Rook configuration
# sudo dmsetup remove_all
ls /dev/mapper/ceph-* | xargs -I% -- sudo dmsetup remove %
sudo rm -rf /dev/ceph-*
sudo rm -rf /dev/mapper/ceph--*
