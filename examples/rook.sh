#!/bin/bash

# Reset k8s
sudo kubeadm reset -f
sudo rm -rf /etc/cni/net.d
sudo ipvsadm --clear

# Cleanup Rook configuration
sudo rm -rf /dev/ceph-*
sudo rm -rf /dev/mapper/ceph--*
sudo rm -rf /var/lib/rook

# Initialize cluster
sudo kubeadm init

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

# Configuration
export ROOK_VERSION=1.2.7

# Installation function
function apply {
    path=$1
    curl "https://raw.githubusercontent.com/rook/rook/v${ROOK_VERSION}/cluster/examples/kubernetes/ceph/${path}" | sed -z "s#\(name: ROOK_ENABLE_DISCOVERY_DAEMON\n[^\n]*value: \)\"false\"#\1\"true\"#g" | kubectl apply -f -
    sleep 1
}

# Install rook-ceph
apply "crds.yaml"
apply "common.yaml"
apply "operator.yaml"
apply "cluster-test.yaml"
apply "csi/rbd/storageclass-test.yaml"
apply "toolbox.yaml"
kubectl -n rook-ceph rollout status deploy/rook-ceph-tools
kubectl patch storageclass rook-ceph-block -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
