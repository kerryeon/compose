import os
import shutil
import urllib3
import yaml

from context import *


FILES = [
    'crds.yaml',
    'common.yaml',
    'operator.yaml',
    'cluster.yaml',
    'csi/rbd/storageclass.yaml',
    'toolbox.yaml',
]

DESTINATION = './.compose/rook'


def collect_dependencies(service: Service) -> set:
    result = set()
    if 'cas' in service.desc:
        result.add('cas')
    return result


def download_file(config: Config, version: str, path: str) -> str:
    filename = path.split('/')[-1]
    url = f'https://raw.githubusercontent.com/rook/rook/v{version}/cluster/examples/kubernetes/ceph/{path}'
    dst = f'./tmp/rook/{filename}'

    http = urllib3.PoolManager()
    with open(dst, 'wb') as out:
        r = http.request('GET', url, preload_content=False)
        shutil.copyfileobj(r, out)
    return dst


def download_files(config: Config, version: str) -> list:
    os.makedirs('./tmp/rook', mode=0o755, exist_ok=True)
    return [download_file(config, version, name) for name in FILES]


def modify(config: Config, service: Service):
    value = service.desc.get('osdsPerDevice')
    value = int(value) if value is not None else 1
    metadata = service.desc.get('metadata')

    num_nodes = min(3, len(config.nodes.all()))
    num_mons = ((num_nodes + 1) // 2) * 2 - 1

    # operator.yaml
    with open('./tmp/rook/operator.yaml', 'r') as f:
        context = list(yaml.load_all(f, Loader=yaml.SafeLoader))
        context[0]['data']['ROOK_ENABLE_DISCOVERY_DAEMON'] = 'true'
    with open('./tmp/rook/operator.yaml', 'w') as f:
        yaml.dump_all(context, f, Dumper=yaml.SafeDumper)

    # cluster.yaml
    num_osds = 0
    with open('./tmp/rook/cluster.yaml', 'r') as f:
        context = yaml.load(f, Loader=yaml.SafeLoader)
        context['spec']['mon']['count'] = num_mons

        storage = context['spec']['storage']
        if 'config' not in storage or storage['config'] is None:
            storage['config'] = {}
        storage['config']['osdsPerDevice'] = str(value)

        storage.setdefault('nodes', [])
        for node in config.nodes.all():
            storge_config = {}
            storge_devices = []
            for name, volume in config.nodes.volumes(node).items():
                if volume.type == metadata:
                    storge_config['metadataDevice'] = name
                else:
                    num_osds += 1
                    storge_devices.append(name)
            storage['nodes'].append({
                'name': node,
                'config': storge_config,
                'devices': storge_devices,
            })
    with open('./tmp/rook/cluster.yaml', 'w') as f:
        yaml.dump(context, f, Dumper=yaml.SafeDumper)

    # storageclass.yaml
    with open('./tmp/rook/storageclass.yaml', 'r') as f:
        context = list(yaml.load_all(f, Loader=yaml.SafeLoader))
        replicated = context[0]['spec']['replicated']
        replicated['size'] = num_nodes
        replicated['requireSafeReplicaSize'] = num_osds > 1
    with open('./tmp/rook/storageclass.yaml', 'w') as f:
        yaml.dump_all(context, f, Dumper=yaml.SafeDumper)


def upload_files(config: Config) -> list:
    files = [f.split('/')[-1] for f in FILES]
    files = {f'./tmp/rook/{f}': f'{DESTINATION}/{f}' for f in files}
    config.command_master(f'mkdir -p {DESTINATION}')
    config.upload_master(files)
    return list(files.values())


def apply(config: Config, service: Service, files: list):
    script = 'kubectl apply ' + ' '.join(f'-f {f}'for f in files)
    script += '\nkubectl patch storageclass rook-ceph-block -p \'{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}\''
    script += '\nkubectl -n rook-ceph rollout status deploy/rook-ceph-tools'
    config.command_master(script)


def compose(config: Config, service: Service):
    download_files(config, service.version)
    modify(config, service)
    files = upload_files(config)
    apply(config, service, files)
