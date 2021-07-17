from bs4 import BeautifulSoup
import glob
import numpy as np
import pandas as pd
import plotly.graph_objs as go
import os
import shutil
import tarfile
import urllib3
import yaml

from context import *
from .generator import Generator

DEPENDENCY_PROGRAM = 'true'


FILES = [
    'crds.yaml',
    'common.yaml',
    'operator.yaml',
    'cluster.yaml',
    'csi/rbd/storageclass.yaml',
    'toolbox.yaml',
]

SOURCE = './tmp/rook'
DESTINATION = './.compose/rook'


def collect_dependencies(service: Service) -> set:
    result = set()
    if 'cas' in service.desc:
        result.add('cas')
    return result


def download_file(config: Config, version: str, path: str) -> str:
    filename = path.split('/')[-1]
    url = f'https://raw.githubusercontent.com/rook/rook/v{version}/cluster/examples/kubernetes/ceph/{path}'
    dst = f'{SOURCE}/{filename}'

    http = urllib3.PoolManager()
    with open(dst, 'wb') as out:
        r = http.request('GET', url, preload_content=False)
        shutil.copyfileobj(r, out)
    return dst


def download_files(config: Config, version: str) -> list:
    os.makedirs(SOURCE, mode=0o755, exist_ok=True)
    return [download_file(config, version, name) for name in FILES]


def modify(config: Config, service: Service):
    osds_per_device = service.desc.get('osdsPerDevice')
    osds_per_device = int(osds_per_device) \
        if osds_per_device is not None else 1

    metadata = service.desc.get('metadata')
    if isinstance(metadata, list):
        pass
    elif isinstance(metadata, str):
        metadata = [metadata]
    elif metadata is None:
        metadata = []
    else:
        raise Exception(f'malformed metadata: {metadata}')

    # operator.yaml
    with open(f'{SOURCE}/operator.yaml', 'r') as f:
        context = list(yaml.load_all(f, Loader=yaml.SafeLoader))
        context[0]['data']['ROOK_ENABLE_DISCOVERY_DAEMON'] = 'true'
        context[1]['spec']['template']['spec']['hostNetwork'] = True
        for env in context[1]['spec']['template']['spec']['containers'][0]['env']:
            if env['name'] == 'ROOK_HOSTPATH_REQUIRES_PRIVILEGED':
                env['value'] = "true"
                break
    with open(f'{SOURCE}/operator.yaml', 'w') as f:
        yaml.dump_all(context, f, Dumper=yaml.SafeDumper)

    # cluster.yaml
    with open(f'{SOURCE}/cluster.yaml', 'r') as f:
        context = yaml.load(f, Loader=yaml.SafeLoader)

        # specify the fixed ceph version
        ceph_image = service.desc.get('cephImage')
        if ceph_image is not None:
            ceph_image_user = ceph_image.get('user') or 'ceph'
            ceph_image_version = ceph_image.get('version')
            if ceph_image_version is not None:
                context['spec']['cephVersion']['image'] = f'{ceph_image_user}/ceph:v{ceph_image_version}'

        # specify the ceph cluster network plane
        context['spec']['network'] = {
            'provider': 'host',
        }

        # specify the disks for ceph cluster
        storage = context['spec']['storage']
        if 'config' not in storage or storage['config'] is None:
            storage['config'] = {}
        storage['useAllNodes'] = False
        storage['useAllDevices'] = False
        storage['deviceFilter'] = ''

        num_nodes = 0
        storage.setdefault('nodes', [])
        for node in config.nodes.all():
            volumes = [v for v in config.nodes.volumes(node) if v.usable]
            storage_config = {}
            storage_devices = []

            if not volumes:
                config.logger.info(f'Skipping Rook-Ceph Node: {node}')
                continue

            # specify the mode
            mode = service.desc.get('mode')
            if mode is not None:
                is_raw_mode = str(mode).upper() == 'RAW'
            else:
                # RAW mode is supported as of 1.6
                is_raw_mode = service.version >= '1.6' and \
                    not any(v.type in metadata for v in volumes)
            mode_name = 'RAW' if is_raw_mode else 'LVM'
            config.logger.info(
                f'Creating Rook-Ceph Node: {node} - [{len(volumes)}] {mode_name} mode')

            # RAW mode
            if is_raw_mode:
                for volume in volumes:
                    num_blocks = int(config.command(
                        node, f'''
                            sudo wipefs --all /dev/{volume.name} && sync
                            sudo sgdisk --zap-all --clear --mbrtogpt /dev/{volume.name} && sync
                            sudo sgdisk --zap-all /dev/{volume.name} && sync
                            sudo dd if=/dev/zero of=/dev/{volume.name} bs=1M count=1 oflag=direct,dsync && sync
                            sudo blkdiscard /dev/{volume.name} && sync
                            sudo sgdisk -Go /dev/{volume.name} && sync
                            sudo sgdisk /dev/{volume.name} -E
                        ''')[-1])
                    for i in range(1, osds_per_device+1):
                        ptr_start = max(
                            2048, int(num_blocks * ((i-1) / osds_per_device)))
                        ptr_end = int(num_blocks * (i / osds_per_device))
                        config.command(
                            node, f'''
                                sudo sgdisk /dev/{volume.name} -n {i}:{ptr_start}:{ptr_end} && sync
                                sudo dd if=/dev/zero of=/dev/{volume.name}p{i} bs=1M count=100 oflag=direct,dsync && sync
                                sudo partprobe /dev/{volume.name}p{i} && sync
                        ''')
                        storage_devices.append({
                            'name': f'{volume.name}p{i}',
                            'config': {
                                'osdsPerDevice': '1',
                            },
                        })
                    config.command(
                        node, f'sudo partprobe /dev/{volume.name} && sync')
            # LVM mode
            else:
                for volume in volumes:
                    if volume.type in metadata:
                        storage_config['metadataDevice'] = volume.name
                    else:
                        storage_devices.append({
                            'name': volume.name,
                            'config': {
                                'osdsPerDevice': str(osds_per_device),
                            },
                        })

            if storage_devices:
                num_nodes += 1
                storage['nodes'].append({
                    'name': node,
                    'config': storage_config,
                    'devices': storage_devices,
                })

        num_nodes = min(3, num_nodes)
        num_mons = ((num_nodes + 1) // 2) * 2 - 1
        context['spec']['mon']['count'] = num_mons

    with open(f'{SOURCE}/cluster.yaml', 'w') as f:
        yaml.dump(context, f, Dumper=yaml.SafeDumper)

    # storageclass.yaml
    with open(f'{SOURCE}/storageclass.yaml', 'r') as f:
        context = list(yaml.load_all(f, Loader=yaml.SafeLoader))
        replicated = context[0]['spec']['replicated']
        replicated['size'] = num_nodes
        replicated['requireSafeReplicaSize'] = num_nodes > 2
    with open(f'{SOURCE}/storageclass.yaml', 'w') as f:
        yaml.dump_all(context, f, Dumper=yaml.SafeDumper)


def upload_files(config: Config) -> list:
    files = [f.split('/')[-1] for f in FILES]
    files = {f'{SOURCE}/{f}': f'{DESTINATION}/{f}' for f in files}
    config.command_master(f'mkdir -p {DESTINATION}')
    config.upload_master(files)
    return list(files.values())


def apply(config: Config, files: list):
    script = ''
    for file in files:
        script += f'\nkubectl apply -f {file}'
        if file.startswith('operator'):
            script += '\nkubectl -n rook-ceph rollout status deploy/rook-ceph-operator'
            script += '\nsleep 60'
        else:
            script += '\nsleep 1'
    script += '\nkubectl -n rook-ceph rollout status deploy/rook-ceph-tools'
    # script += '\nkubectl -n rook-ceph create secret generic rook-ceph-crash-collector-keyring'
    script += '\nkubectl patch storageclass rook-ceph-block -p \'{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}\''
    config.command_master(script)


def compose(config: Config, service: Service):
    download_files(config, service.version)
    modify(config, service)
    files = upload_files(config)
    apply(config, files)


def shutdown(config: Config, service: Service):
    files = [f'{DESTINATION}/{f.split("/")[-1]}' for f in reversed(FILES)]
    script = ''
    for file in files:
        script += f'\nkubectl delete -f {file} --timeout=30s'
        script += '\nsleep 1'
    config.command_master(script)

    with open(f'./services/kubernetes/shutdown-volumes.sh') as f:
        script = '\n' + ''.join(f.readlines())
    config.command_all(script,
                       volumes=config.volumes_str(config.nodes.master.name))


def benchmark(config: Config, benchmark: Benchmark, name: str):
    filename = f'{name}.tar'

    src_dir = f'{DESTINATION}/{name}'
    src = f'{DESTINATION}/{filename}'
    dst_dir = './outputs'
    dst = f'{dst_dir}/{filename}'

    # generate script.ini
    vdbench = benchmark.desc['vdbench']
    generator = Generator(
        depth=vdbench.get('depth') or 2,
        width=vdbench.get('width') or 16,
        file=vdbench.get('file') or 32,
        size=vdbench.get('size') or '4M',
        threads=vdbench.get('rbds') or 20,
        num_rbds=vdbench.get('rbds') or 20,
        rbd_size=vdbench.get('rbdSize') or '64Gi',
    )

    # taint the node
    node = benchmark.desc.get('node')
    node = str(node) if node is not None else None
    if node is not None:
        config.command_master(f'kubectl label nodes {node} benchmarker=true')

    # generate & upload the yaml script
    os.makedirs(SOURCE, mode=0o755, exist_ok=True)
    with open(f'{SOURCE}/benchmark.yaml', 'w') as f:
        generator.generate_yaml(f, taint=node is not None)
    config.command_master(f'mkdir -p {DESTINATION}')
    config.upload_master({
        f'{SOURCE}/benchmark.yaml': f'{DESTINATION}/benchmark.yaml',
    })

    # generate & upload the ini script
    with open(f'{SOURCE}/script.ini', 'w') as f:
        generator.generate_script(f)
    config.upload_master({
        f'{SOURCE}/script.ini': f'{DESTINATION}/script.ini',
    })

    # play
    config.command_master(
        quiet=True,
        script=''
        f'kubectl apply -f {DESTINATION}/benchmark.yaml'
        '\nsleep 1'
        '\nexport pod_name=$(kubectl get pods --no-headers -o custom-columns=":metadata.name" | grep "vdbench-")'
        '\nkubectl wait --for=condition=ready --timeout=24h pod ${pod_name}'
        # inject the generated script
        f'\nkubectl cp "{DESTINATION}/script.ini" ${{pod_name}}:script.ini'
        '\nkubectl exec ${pod_name} -- ./vdbench -f script.ini -o output'
        f'\nkubectl cp ${{pod_name}}:output "{src_dir}"'
        f'\npushd "{src_dir}" && tar cf "../{filename}" * && popd'
    )

    # take the result
    config.logger.info(f'Saving result: {dst}')
    os.makedirs(dst_dir, exist_ok=True)
    config.download_master({src: dst})

    # shutdown
    config.logger.info(f'Finalizing benchmark: {name}')
    config.command_master(f'kubectl delete -f {DESTINATION}/benchmark.yaml')


def visualize(gui: bool):
    def _find_header(data: list) -> int:
        for index, line in enumerate(data):
            if line.find('cpu') != -1:
                return index

    def _parse_header(data: list, index: int) -> list:
        fields = []
        num_fields = []

        # first line
        for word in data[index].split('.')[1:]:
            word_strip = word.strip()
            if not word_strip:
                continue
            fields.append((word_strip, []))
            num_fields.append(
                2 if word == word_strip and word != 'xfer' else 1)

        # second line
        index_field = 1  # skip the first field: Interval
        for word in data[index+1].split(' '):
            if not word:
                continue
            fields[index_field][1].append(word.strip())
            num_fields[index_field] -= 1
            if not num_fields[index_field]:
                index_field += 1

        result = ['rd_name']
        for name, contents in fields:
            for content in contents:
                result.append(f'{name}_{content}')
        return result

    def _parse_data(data: list, index: int) -> dict:
        result = {}

        name = None
        values = None
        for line in data[index:]:
            line = line.strip()
            if not line:
                continue
            for word in line.split(' '):
                if not word:
                    continue
                if word.startswith('RD='):
                    name = word[3:-1]
                    if not name.startswith('rd_'):
                        name = None
                    break
                if word.startswith('avg_'):
                    if not name:
                        break
                    values = []
                    continue
                if values is not None:
                    values.append(word)
            if name and values:
                result[name] = np.asarray(values, dtype=np.float64)
                name = None
                values = None
        return result

    def _attach_labels(label: str, df):
        df['benchmark.label'] = label

        # parse config
        with open(f'./outputs/metadata/{label}.yaml') as f:
            context = yaml.load(f, Loader=yaml.SafeLoader)
        df['service.rook.numNodes'] = len(context['nodes']['desc'])
        service = next(svc for svc in context['services']
                       if svc['name'] == 'rook')
        df['service.rook.metadata'] = ','.join(service['desc']['metadata'])
        df['service.rook.version'] = service['version']

        df['service.rook.desc.mode'] = service['desc'].get('mode')
        df['service.rook.desc.osdsPerDevice'] = int(
            service['desc']['osdsPerDevice'])
        ceph_image = service['desc'].get('cephImage')
        if ceph_image is not None:
            df['service.rook.desc.cephImage.user'] = ceph_image.get('user')
            df['service.rook.desc.cephImage.version'] = ceph_image.get(
                'version')
        else:
            df['service.rook.desc.cephImage.user'] = None
            df['service.rook.desc.cephImage.version'] = None

        benchmark = context['benchmark']['desc']
        df['benchmark.node'] = benchmark['node']

        vdbench = benchmark['vdbench']
        df['benchmark.vdbench.depth'] = vdbench['depth']
        df['benchmark.vdbench.width'] = vdbench['width']
        df['benchmark.vdbench.file'] = vdbench['file']
        df['benchmark.vdbench.size'] = vdbench['size']
        df['benchmark.vdbench.rbds'] = vdbench['rbds']
        df['benchmark.vdbench.rbdSize'] = vdbench['rbdSize']

        # parse config: cas
        services_cas = [svc for svc in context['services']
                        if svc['name'] == 'cas']
        if services_cas:
            if len(services_cas) != 1:
                raise Exception(
                    '2 or more CAS settings at once is not supported.'
                )
            for service_cas in services_cas:
                if len(service_cas['desc']) != 1:
                    raise Exception(
                        '2 or more CAS devices at once is not supported.'
                    )
                for config in service_cas['desc']:
                    enabled = service_cas.get('enabled') != False
                    df['service.cas.enabled'] = enabled
                    if not enabled:
                        continue
                    df['service.cas.cache'] = str(config['cache'])
                    df['service.cas.devices'] = str(set(config['devices']))
                    df['service.cas.mode'] = str(config['mode'])
        else:
            df['service.cas.enabled'] = False
        return df

    def _print_data(header: list, data: dict):
        print(''.join(f'{word:^16}' for word in header))
        for name, content in data.items():
            print(f'{name:^16}', end='')
            print(''.join(f'{word:^16}' for word in content))

    def _to_data_frame(label: str, header: list, data: dict):
        df = pd.DataFrame(
            [[k, *v] for k, v in data.items()],
            columns=[f'benchmark.result.{c}' for c in header],
        )
        df['benchmark.result.iops'] = df['benchmark.result.read_rate'] + \
            df['benchmark.result.write_rate']
        return _attach_labels(label, df)

    dfs = []
    labels = []
    for file in glob.glob('./outputs/*.tar'):
        try:
            # load a file
            with tarfile.open(file) as tar:
                data = tar.extractfile('totals.html').read()

            # parse data
            soup = BeautifulSoup(data, 'html.parser')
            data = soup.prettify().split('\n')

            # find header
            header_index = _find_header(data)
            header = _parse_header(data, header_index)

            # find data
            data = _parse_data(data, header_index+2)

            # print data
            # _print_data(header, data)

            # make a data frame
            label = file.split('/')[-1][:-4]
            labels.append(label)
            df = _to_data_frame(label, header, data)
            dfs.append(df)
        except Exception as e:
            print(f'- Failed to parse the file: "{file}"', file=sys.stderr)
            raise e

    # merge data frames
    df = pd.concat(dfs)
    df = df.reset_index(drop=True)
    df.index.name = 'index'

    # store result to .csv file
    labels.sort()
    os.makedirs('./outputs/results', exist_ok=True)
    df.to_csv(f'./outputs/results/{labels[0]}_{labels[-1]}.csv')

    # visualize data
    if gui:
        rd_names = sorted(df['benchmark.result.rd_name'].unique())
        rbds = sorted(df['benchmark.vdbench.rbds'].unique())

        data = []
        for index, rd_name in enumerate(rd_names):
            df_rd = df[df['benchmark.result.rd_name'] == rd_name]
            for rbd in rbds:
                df_rbd = df_rd[df_rd['benchmark.vdbench.rbds'] == rbd]
                data.append(go.Bar(
                    x=sorted(str(x)
                             for x in df_rbd['service.rook.desc.osdsPerDevice'].unique()),
                    y=df_rbd['benchmark.result.mb/sec_total'],
                    name=f'{rbd} rbds',
                    visible=index == 0,
                ))

        buttons = []
        for index, rd_name in enumerate(rd_names):
            index = index * len(rbds)
            visible = np.array([False] * len(rd_names) * len(rbds))
            visible[index: index+len(rbds)] = True
            buttons.append({
                'label': rd_name,
                'method': 'update',
                'args': [
                    {
                        'visible': visible,
                    },
                ],
            })

        layout = {
            'xaxis': {
                'title': 'OsdsPerDevice',
            },
            'yaxis': {
                'title': 'MB/s',
            },
            'updatemenus': [{
                'buttons': buttons,
                'direction': 'down',
                'showactive': True,
                'xanchor': 'right',
                'yanchor': 'top',
            }],
        }

        fig = go.Figure(data=data, layout=layout)
        fig.show()
