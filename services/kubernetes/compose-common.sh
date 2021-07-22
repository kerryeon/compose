#!/bin/bash

# Clean up the cluster (only in master)
kubectl delete --all pods 2>/dev/null || true
kubectl delete --all all 2>/dev/null || true

# Reset k8s
sudo kubeadm reset -f
sudo rm -rf /etc/cni/net.d
sudo ipvsadm --clear

for i in $(systemctl list-unit-files --no-legend --no-pager -l | grep --color=never -o -e ".*.slice" | grep kubepod); do
    sudo systemctl stop $i
done
