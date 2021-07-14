#!/bin/bash

# (Install Docker CE)
## Set up the repository:
### Install packages to allow apt to use a repository over HTTPS
sudo yum install -y \
    yum-utils \
    device-mapper-persistent-data \
    lvm2

# Add the Docker rpm repository:
sudo yum-config-manager --add-repo "https://download.docker.com/linux/centos/docker-ce.repo"

# Install Docker CE
sudo yum install -y \
    docker-ce

## Create /etc/docker
sudo mkdir -p /etc/docker

# Set up the Docker daemon
cat <<EOF | sudo tee /etc/docker/daemon.json
{
    "exec-opts": ["native.cgroupdriver=systemd"],
    "log-driver": "json-file",
    "log-opts": { "max-size": "100m" },
    "storage-driver": "overlay2"
}
EOF

# Turn off the firewalld
sudo systemctl disable --now firewalld

# Update iptables settings
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-ip6tables = 1
net.bridge.bridge-nf-call-iptables = 1
EOF
sudo sysctl --system

# Create /etc/systemd/system/docker.service.d
sudo mkdir -p /etc/systemd/system/docker.service.d

sudo systemctl daemon-reload
sudo systemctl enable docker
sudo systemctl restart docker
sudo systemctl restart docker.socket
