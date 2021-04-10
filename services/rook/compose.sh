#!/bin/bash

kubectl create -f $svc_home/crds.yaml
kubectl create -f $svc_home/common.yaml
kubectl create -f $svc_home/operator.yaml

kubectl create -f $svc_home/cluster.yaml
kubectl create -f $svc_home/csi/rbd/storageclass.yaml

kubectl create -f $svc_home/toolbox.yaml
kubectl -n rook-ceph rollout status deploy/rook-ceph-tools
