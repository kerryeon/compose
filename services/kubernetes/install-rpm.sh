#!/bin/bash

# Turn-off swap (virtual memory)
sudo swapoff -a
sudo sed -e '/\/dev\/mapper\/rl-swap/s/^/#/g' -i /etc/fstab

# Install kubernetes
sudo yum install -y \
    ipvsadm \
    parted \
    gdisk

cat <<EOF | sudo tee /etc/yum.repos.d/kubernetes.repo
[kubernetes]
name=Kubernetes
baseurl=https://packages.cloud.google.com/yum/repos/kubernetes-el7-x86_64
enabled=1
gpgcheck=1
repo_gpgcheck=1
gpgkey=https://packages.cloud.google.com/yum/doc/yum-key.gpg https://packages.cloud.google.com/yum/doc/rpm-package-key.gpg
EOF

sudo yum install -y --disableexcludes=kubernetes \
    kubelet \
    kubeadm \
    kubectl

sudo systemctl enable --now systemd-resolved
sudo systemctl enable --now kubelet
