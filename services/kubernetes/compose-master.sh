#!/bin/bash

# Initialize cluster with D-plane
sudo kubeadm init --apiserver-advertise-address $node_ip

rm -r $HOME/.kube
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# Schedule master node (=control plane node)
kubectl taint nodes --all node-role.kubernetes.io/master-

# Apply Network Policy (CNI)
kubectl apply -f "https://cloud.weave.works/k8s/net?k8s-version=$(kubectl version | base64 | tr -d '\n')"

# Remove RBAC
kubectl create clusterrolebinding permissive-binding \
    --clusterrole=cluster-admin \
    --user=admin \
    --user=kubelet \
    --group=system:serviceaccounts
