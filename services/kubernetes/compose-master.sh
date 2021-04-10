#!/bin/bash

# Reset k8s
sudo kubeadm reset -f
sudo rm -rf /etc/cni/net.d
sudo ipvsadm --clear

# Cleanup Rook configuration
sudo rm -rf /var/lib/rook
sudo dmsetup remove_all
sudo wipefs --all /dev/nvme0n1 /dev/nvme1n1

# Initialize cluster with D-plane
sudo kubeadm init --apiserver-advertise-address $K8S_IP

rm -r $HOME/.kube
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# Schedule master node (=control plane node)
kubectl taint nodes --all node-role.kubernetes.io/master-
