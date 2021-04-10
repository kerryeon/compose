#!/bin/bash

# Reset k8s
sudo kubeadm reset -f
sudo rm -rf /etc/cni/net.d
sudo ipvsadm --clear

# Cleanup Rook configuration
sudo rm -rf /var/lib/rook
sudo dmsetup remove_all
sudo wipefs --all $volumes
