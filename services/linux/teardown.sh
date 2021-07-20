#!/bin/bash

sudo systemctl stop docker docker.socket
sudo kubeadm reset -f
sudo reboot
