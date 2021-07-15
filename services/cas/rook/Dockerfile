FROM ceph/ceph:v15.2.7

RUN sed -i 's/# types = \[ "fd", 16 \]/types = \[ "cas", 16 \]/g' /etc/lvm/lvm.conf
RUN sed -i '0,/# filter = \[ "a|.*|" \]/ s/# filter = \[ "a|.*|" \]/filter = \[ "a|.*|" \]/' /etc/lvm/lvm.conf

CMD ["/bin/bash"]
