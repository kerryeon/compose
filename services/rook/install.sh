#!/bin/bash
# note: This installation script is for development, not for production.
# So, be careful of using it.

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
