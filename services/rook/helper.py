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
    osds_per_device = service.desc.get('osdsPerDevice')
    osds_per_device = int(osds_per_device) \
        if osds_per_device is not None else 1
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
        storage['config']['osdsPerDevice'] = str(osds_per_device)

        storage.setdefault('nodes', [])
        for node in config.nodes.all():
            storge_config = {
                # 'osdsPerDevice': str(osds_per_device),
            }
            storge_devices = []
            for name, volume in config.nodes.volumes(node).items():
                if volume.type == metadata:
                    storge_config['metadataDevice'] = name
                else:
                    num_osds += 1
                    storge_devices.append({'name': name})
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


def apply(config: Config, files: list):
    script = ''
    for file in files:
        script += f'\nkubectl create -f {file}'
        script += '\nsleep 1'
    script += '\nkubectl -n rook-ceph rollout status deploy/rook-ceph-tools'
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
        script += f'\nkubectl delete -f {file}'
        script += '\nsleep 1'
    config.command_master(script)

    with open(f'./services/kubernetes/shutdown-volumes.sh') as f:
        script = '\n' + ''.join(f.readlines())
    config.command_all(script,
                       volumes=config.volumes_str(config.nodes.master))


def benchmark(config: Config, name: str):
    from datetime import date
    url = 'https://raw.githubusercontent.com/kerryeon/rook-bench/master/rook-bench.yaml'

    time = date.today().strftime('%d/%m/%Y-%H:%M:%S')
    filename = f'{name}-{time}.tar'

    # play
    config.command_master(
        quiet=True,
        script=''
        f'kubectl create -f {url}'
        '\nsleep 1'
        '\nexport pod_name=$(kubectl get pods --no-headers -o custom-columns=":metadata.name" | grep "vdbench-")'
        '\nkubectl wait --for=condition=ready --timeout=24h pod ${pod_name}'
        '\nkubectl exec ${pod_name} -- ./vdbench -f script.ini -o output >/dev/null'
        f'\nkubectl cp ${{pod_name}}:output {DESTINATION}/{time}'
        f'\ntar xf {DESTINATION}/{filename} {DESTINATION}/{time}'
    )

    # take the result
    os.makedirs('./outputs', exist_ok=True)
    config.download_master({
        f'{DESTINATION}/{filename}': f'outputs/{filename}',
    })

    # shutdown
    config.command_master(f'kubectl delete -f {url}')
