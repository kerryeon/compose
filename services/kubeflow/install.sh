#!/bin/bash

# Set work directory
export BASE_DIR=$HOME/.compose/kubeflow
mkdir -p $BASE_DIR && pushd $BASE_DIR

# Install kfctl
export KFCTL_VERSION=0.7.1
export KFCTL_FILE=kfctl_v${KFCTL_VERSION}-2-g55f9b2a_linux.tar.gz
wget https://github.com/kubeflow/kfctl/releases/download/v${KFCTL_VERSION}/${KFCTL_FILE}
tar -xf $KFCTL_FILE && rm $KFCTL_FILE
sudo mv kfctl /usr/local/bin/kfctl
popd

# Configuration
export KF_NAME="kubeflow-demo"
export KF_DIR=${BASE_DIR}/${KF_NAME}
export PATH=$PATH:$BASE_DIR
export CONFIG_URL="https://raw.githubusercontent.com/kubeflow/manifests/v0.7-branch/kfdef/kfctl_k8s_istio.${KFCTL_VERSION}.yaml"

# Install kubeflow
rm -rf $KF_DIR; mkdir -p $KF_DIR; pushd $KF_DIR
kfctl apply -V -f $CONFIG_URL
popd
