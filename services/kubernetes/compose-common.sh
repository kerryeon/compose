#!/bin/bash

# Clean up the cluster
kubectl delete --all pods 2>/dev/null

# Reset k8s
sudo kubeadm reset -f
sudo rm -rf /etc/cni/net.d
sudo ipvsadm --clear
