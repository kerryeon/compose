#!/bin/bash

# Turn-off swap (virtual memory)
sudo swapoff -a
sudo sed -e '/\/swapfile/s/^/#/g' -i /etc/fstab
sudo sed -e '/\/swap\.img/s/^/#/g' -i /etc/fstab

# Install kubernetes
sudo apt update -q && sudo apt install -qy \
    apt-transport-https \
    curl \
    ipvsadm \
    wget

cat <<EOF | sudo tee /etc/apt/sources.list.d/kubernetes.list
deb http://apt.kubernetes.io/ kubernetes-xenial main
EOF

curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -

sudo apt update -q && sudo apt install -qy --allow-downgrades --allow-change-held-packages \
    kubelet \
    kubeadm \
    kubectl \
    kubernetes-cni

# Set a default Node IP
Environment="KUBELET_CONFIG_ARGS=--config=/var/lib/kubelet/config.yaml --node-ip=${NODE_IP}"
