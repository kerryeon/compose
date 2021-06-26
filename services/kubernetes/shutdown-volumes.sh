#!/bin/bash

# Cleanup LVMs
for volume in $volumes; do
    sudo sgdisk --zap-all $volume && sync
    sudo dd if=/dev/zero of=$volume bs=512 count=4096 conv=notrunc && sync
    sudo mkfs.ext4 $volume && sync
    sudo wipefs --all $volume && sync
    sudo dd if=/dev/zero of=$volume bs=512 count=4096 conv=notrunc && sync
    sudo blkdiscard $volume && sync
done

# Cleanup Rook configuration
# sudo dmsetup remove_all
ls /dev/mapper/ceph-* | xargs -I% -- sudo dmsetup remove %
sudo rm -rf /dev/ceph-*
sudo rm -rf /dev/mapper/ceph--*
sudo rm -rf /var/lib/rook/
sudo rm -rf /var/lib/kubelet/plugins/
sudo rm -rf /var/lib/kubelet/plugins_registry/

# Update tables
for volume in $volumes; do
    sudo partprobe $volume && sync
done
