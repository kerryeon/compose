#!/bin/bash

# Clean up the cluster (only in master)
kubectl delete --all --grace-period=0 --force pods 2>/dev/null || true
kubectl delete --all all 2>/dev/null || true

# Reset k8s
sudo kubeadm reset -f
sudo rm -rf /etc/cni/net.d
sudo ipvsadm --clear
