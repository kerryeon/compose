import io


FWD_MODES = [
    ('rr_4k', 'read', '4k', 'random'),
    ('rw_4k', 'write', '4k', 'random'),
    ('sr_512k', 'read', '512k', 'sequential'),
    ('sw_512k', 'write', '512k', 'sequential'),
]


class Generator:
    def __init__(self, depth: int, width: int, file: int,
                 size: str, threads: int, num_rbds: int,
                 rbd_size: str,
                 ):
        self.depth = depth
        self.width = width
        self.file = file
        self.size = size
        self.threads = threads

        self.num_rbds = num_rbds
        self.rbd_size = rbd_size

    def generate_script(self, stream=None) -> str:
        if stream is None:
            stream = io.StringIO()

        def write(*args, **kwargs): return print(*args, **kwargs, file=stream)

        # hd
        write('hd=default,user=root')
        write('hd=localhost')
        write()

        # fsd
        write(
            f'fsd=default,depth={self.depth},width={self.width},file={self.file},size={self.size}'
        )
        for i in range(1, self.num_rbds + 1):
            write(f'fsd=fsd{i},anchor=/mnt/bench{i}')
        write()

        # fwd
        write(
            f'fwd=default,host=localhost,threads={self.threads},fileselect=random'
        )
        for name, op, xfer, fileio in FWD_MODES:
            for i in range(1, self.num_rbds + 1):
                write(
                    f'fwd=fwd_{name}_{i},fsd=fsd{i},operation={op},xfersize={xfer},fileio={fileio}'
                )
        write()

        # rd
        write('rd=default,fwdrate=max,interval=1,elapsed=600')
        for name, op, xfer, fileio in FWD_MODES:
            fwds = ','.join(
                f'fwd_{name}_{i}' for i in range(1, self.num_rbds + 1)
            )
            write(f'rd=rd_{name},fwd=({fwds}),format=yes')
        write()

        if isinstance(stream, io.StringIO):
            stream.flush()
            stream.seek(0)
            return stream.read()
        return None

    def generate_yaml(self, stream=None):
        if stream is None:
            stream = io.StringIO()

        def write(*args, **kwargs): return print(*args, **kwargs, file=stream)

        # PVC
        for i in range(1, self.num_rbds + 1):
            write('---')
            write('apiVersion: v1')
            write('kind: PersistentVolumeClaim')
            write('metadata:')
            write('  name: vdbench-pvc-claim-1')
            write('spec:')
            write('  storageClassName: rook-ceph-block')
            write('  accessModes:')
            write('    - ReadWriteOnce')
            write('  resources:')
            write('    requests:')
            write(f'      storage: {self.rbd_size}')

        # PVC
        for i in range(1, self.num_rbds + 1):
            write('---')
            write('apiVersion: v1')
            write('kind: PersistentVolumeClaim')
            write('metadata:')
            write(f'  name: vdbench-pvc-claim-{i}')
            write('spec:')
            write('  storageClassName: rook-ceph-block')
            write('  accessModes:')
            write('    - ReadWriteOnce')
            write('  resources:')
            write('    requests:')
            write(f'      storage: {self.rbd_size}')

        # Job
        write('---')
        write('apiVersion: batch/v1')
        write('kind: Job')
        write('metadata:')
        write('  name: vdbench')
        write('spec:')
        write('  template:')
        write('    metadata:')
        write('      name: vdbench')
        write('    spec:')
        write('      restartPolicy: Never')
        write('      containers:')
        write('        - name: vdbench')
        write('          image: kerryeon/rook-bench')
        write('          imagePullPolicy: Always')
        write('          command: [ "/bin/bash", "-c", "--" ]')
        write('          args: [ "while true; do sleep 30; done;" ]')
        write('          volumeMounts:')
        for i in range(1, self.num_rbds + 1):
            write(f'            - name: vdbench-vol-{i}')
            write(f'              mountPath: /mnt/bench{i}')
        write('      volumes:')
        for i in range(1, self.num_rbds + 1):
            write(f'        - name: vdbench-vol-{i}')
            write(f'          persistentVolumeClaim:')
            write(f'            claimName: vdbench-pvc-claim-{i}')

        if isinstance(stream, io.StringIO):
            stream.flush()
            stream.seek(0)
            return stream.read()
        return None
