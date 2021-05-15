FROM ceph/ceph:v15.2.11

RUN sed -i 's/# types = \[ "fd", 16 \]/types = \[ "cas", 16 \]/g' /etc/lvm/lvm.conf

CMD ["/bin/bash"]
