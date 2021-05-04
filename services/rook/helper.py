from bs4 import BeautifulSoup
import glob
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os
import shutil
import tarfile
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
            for volume in config.nodes.volumes(node):
                if not volume.usable:
                    continue
                if volume.type == metadata:
                    storge_config['metadataDevice'] = volume.name
                else:
                    num_osds += 1
                    storge_devices.append({'name': volume.name})
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
        script += f'\nkubectl delete -f {file} --timeout=240s'
        script += '\nsleep 1'
    config.command_master(script)

    with open(f'./services/kubernetes/shutdown-volumes.sh') as f:
        script = '\n' + ''.join(f.readlines())
    config.command_all(script,
                       volumes=config.volumes_str(config.nodes.master))


def benchmark(config: Config, name: str):
    url = 'https://raw.githubusercontent.com/kerryeon/rook-bench/master/rook-bench.yaml'

    filename = f'{name}.tar'

    src_dir = f'{DESTINATION}/{name}'
    src = f'{DESTINATION}/{filename}'
    dst_dir = './outputs'
    dst = f'{dst_dir}/{filename}'

    # play
    config.command_master(
        quiet=True,
        script=''
        f'kubectl create -f {url}'
        '\nsleep 1'
        '\nexport pod_name=$(kubectl get pods --no-headers -o custom-columns=":metadata.name" | grep "vdbench-")'
        '\nkubectl wait --for=condition=ready --timeout=24h pod ${pod_name}'
        # '\nkubectl exec ${pod_name} -- sed -i -e "s/600/3/g" script.ini'
        '\nkubectl exec ${pod_name} -- ./vdbench -f script.ini -o output >/dev/null'
        f'\nkubectl cp ${{pod_name}}:output "{src_dir}"'
        f'\npushd "{src_dir}" && tar cf "../{filename}" * && popd'
    )

    # take the result
    config.logger.info(f'Saving result: {dst}')
    os.makedirs(dst_dir, exist_ok=True)
    config.download_master({src: dst})

    # shutdown
    config.command_master(f'kubectl delete -f {url}')


def visualize():
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
        df['label'] = label

        # parse config
        with open(f'./outputs/metadata/{label}.yaml') as f:
            context = yaml.load(f, Loader=yaml.SafeLoader)
        df['numNodes'] = len(context['nodes']['desc'])
        service = next(svc for svc in context['services']
                       if svc['name'] == 'rook')
        df['osdsPerDevice'] = int(service['desc']['osdsPerDevice'])
        df['metadata'] = service['desc'].get('metadata')

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
                    df['cas_enabled'] = True
                    df['cas_cache'] = str(config['cache'])
                    df['cas_devices'] = str(set(config['devices']))
                    df['cas_mode'] = str(config['mode'])
        else:
            df['cas_enabled'] = False
        return df

    def _print_data(header: list, data: dict):
        print(''.join(f'{word:^16}' for word in header))
        for name, content in data.items():
            print(f'{name:^16}', end='')
            print(''.join(f'{word:^16}' for word in content))

    def _to_data_frame(label: str, header: list, data: dict):
        df = pd.DataFrame(
            [[k, *v] for k, v in data.items()],
            columns=header,
        )
        df['iops'] = df['read_rate'] + df['write_rate']
        return _attach_labels(label, df)

    dfs = []
    labels = []
    for file in glob.glob('./outputs/*.tar'):
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

    # merge data frames
    df = pd.concat(dfs)
    df = df.reset_index(drop=True)
    df.index.name = 'index'

    # store result to .csv file
    labels.sort()
    os.makedirs('./outputs/results', exist_ok=True)
    df.to_csv(f'./outputs/results/{labels[0]}_{labels[-1]}.csv')

    # visualize data
    # frame = df[df['rd_name'] == 'rd_rr_4k']
    # frame.plot(x='label', y='iops')
    # plt.show()
