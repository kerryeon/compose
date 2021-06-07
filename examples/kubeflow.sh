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
export BASE_DIR=$HOME/.compose/kubeflow
export ROOK_VERSION=1.2.7
export KFCTL_VERSION=1.2.0

export KF_NAME="kubeflow-demo"
export KF_DIR=${BASE_DIR}/${KF_NAME}
export PATH=$PATH:$BASE_DIR
export CONFIG_URL="https://raw.githubusercontent.com/kubeflow/manifests/v1.2-branch/kfdef/kfctl_k8s_istio.v${KFCTL_VERSION}.yaml"

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

# Install kfctl
export KFCTL_FILE=kfctl_v${KFCTL_VERSION}-0-gbc038f9_linux.tar.gz
wget https://github.com/kubeflow/kfctl/releases/download/v${KFCTL_VERSION}/${KFCTL_FILE}
tar -xf $KFCTL_FILE && rm $KFCTL_FILE
sudo mv kfctl /usr/local/bin/kfctl
popd

# Install kubeflow
rm -rf $KF_DIR; mkdir -p $KF_DIR; pushd $KF_DIR
kfctl apply -V -f $CONFIG_URL
popd
