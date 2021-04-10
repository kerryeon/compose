from context import *


def _import_helper(name: str, attr: str):
    try:
        module = __import__(f'services.{name}.helper', fromlist=[attr])
        return getattr(module, attr)
    except:
        return None


def eusure_dependency(config: Config, name: str):
    # find installer script
    try:
        with open(f'./services/{name}/install.sh') as f:
            script = '\n'.join(f.readlines())
    except FileNotFoundError:
        return

    # find program name
    program = _import_helper(name, 'DEPENDENCY_PROGRAM') or name

    config.logger.info(f'Checking installation: {name}')
    for node, outputs in config.command_all(f'which {program}'):
        if not outputs:
            config.logger.info(f'Installing {name} on {node}')
            config.command(node, script,
                           install_name=name, install_program=program)


def eusure_dependencies(config: Config):
    for name in config.collect_dependencies():
        eusure_dependency(config, name)


def compose_cluster_master(config: Config):
    # find installer script
    with open(f'./services/kubernetes/compose-master.sh') as f:
        script = '\n'.join(f.readlines())

    config.logger.info(f'Initializing cluster: master ({config.nodes.master})')
    print(config.command_master(script))


def compose_cluster(config: Config):
    print(compose_cluster_master(config))


def install_core(config: Config):
    eusure_dependencies(config)
    compose_cluster(config)
