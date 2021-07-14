#!/bin/bash

# Initialize cluster with D-plane
sudo kubeadm init --apiserver-advertise-address $node_ip --pod-network-cidr 10.85.0.0/16

rm -r $HOME/.kube
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# Schedule master node (=control plane node)
if [ $taint -eq 0 ]; then
    kubectl taint nodes --all node-role.kubernetes.io/master-
fi

# Apply Network Policy (CNI)
kubectl apply -f "https://docs.projectcalico.org/manifests/calico.yaml"

# Remove RBAC
kubectl create clusterrolebinding permissive-binding \
    --clusterrole=cluster-admin \
    --user=admin \
    --user=kubelet \
    --group=system:serviceaccounts
