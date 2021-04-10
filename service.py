from context import *


def _volumes_to_str(config: Config, name: str) -> str:
    return ' '.join(f'/dev/{v}' for v in config.volumes(name).keys())


def select_kubernetes_plane(config: Config) -> str:
    return 'data'


def ensure_root_permission(config: Config):
    import socket

    config.logger.info(f'Checking root permissions')
    for node in config.nodes.all():
        try:
            config.command(node, f'sudo true', timeout=True)
        except socket.timeout:
            config.logger.error(
                f'Failed to access root permission: {node}')
            config.logger.error(
                f'Please make sure to "sudo" without password.')
            config.logger.error(
                f'Note: https://askubuntu.com/a/340669')
            exit(1)


def eusure_dependency(config: Config, name: str):
    # find installer script
    try:
        with open(f'./services/{name}/install.sh') as f:
            script = '\n'.join(f.readlines())
    except FileNotFoundError:
        return

    # find program name
    program = import_helper(name, 'DEPENDENCY_PROGRAM') or name

    config.logger.info(f'Checking installation: {name}')
    for node, outputs in config.command_all(f'which {program}'):
        if not outputs:
            config.logger.info(f'Installing {name} on {node}')
            config.command(node, script, node_ip=config.node_ip(node),
                           install_name=name, install_program=program)


def eusure_dependencies(config: Config):
    for name in config.collect_dependencies():
        eusure_dependency(config, name)


def compose_cluster_master(config: Config):
    # find composing script
    with open(f'./services/kubernetes/compose-common.sh') as f:
        script = '\n'.join(f.readlines())
    with open(f'./services/kubernetes/compose-master.sh') as f:
        script += '\n' + '\n'.join(f.readlines())

    config.logger.info(f'Initializing cluster: master ({config.nodes.master})')
    output = config.command_master(script, node_ip=config.master_node_ip(),
                                   volumes=_volumes_to_str(config, config.nodes.master))

    # parse join command
    for idx, line in enumerate(output):
        if line.startswith('kubeadm join '):
            return 'sudo ' + line.strip()[:-1] + output[idx+1].strip()
    config.logger.error('Failed to initialize cluster')
    exit(1)


def compose_cluster_workers(config: Config, join_command: str):
    # find composing script
    with open(f'./services/kubernetes/compose-common.sh') as f:
        script = '\n'.join(f.readlines())
    script += '\n' + join_command + '\n'

    for name in config.nodes.workers():
        config.logger.info(f'Initializing cluster: worker ({name})')
        print(config.command(name, script, node_ip=config.node_ip(name),
                             volumes=_volumes_to_str(config, name)))


def compose_cluster_services(config: Config):
    for name, service in config.services.all():
        config.logger.info(f'Initializing service: {name}')
        composer = import_helper(name, 'compose')
        composer(config, service)


def compose_cluster(config: Config, reset: bool = True, services: bool = True):
    if reset:
        join_command = compose_cluster_master(config)
        compose_cluster_workers(config, join_command)
    if services:
        compose_cluster_services(config)


def solve(config: Config):
    config.planes.primary = select_kubernetes_plane(config)
    ensure_root_permission(config)
    eusure_dependencies(config)
    # compose_cluster(config)
    compose_cluster(config, reset=False, services=True)
