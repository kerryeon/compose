#!/bin/bash

# Version
https://raw.githubusercontent.com/rook/rook/v1.5.9/cluster/examples/kubernetes/ceph/crds.yaml

# Remove RBAC
kubectl create clusterrolebinding permissive-binding \
    --clusterrole=cluster-admin \
    --user=admin \
    --user=kubelet \
    --group=system:serviceaccounts

kubectl create -f $SVC_HOME/cluster/examples/kubernetes/ceph/crds.yaml
kubectl create -f $SVC_HOME/cluster/examples/kubernetes/ceph/common.yaml
kubectl create -f $SVC_HOME/cluster/examples/kubernetes/ceph/operator.yaml

kubectl create -f $SVC_HOME/cluster/examples/kubernetes/ceph/cluster.yaml

kubectl create -f $SVC_HOME/cluster/examples/kubernetes/ceph/csi/cephfs/storageclass.yaml

kubectl create -f $SVC_HOME/cluster/examples/kubernetes/ceph/toolbox.yaml
kubectl -n rook-ceph rollout status deploy/rook-ceph-tools
