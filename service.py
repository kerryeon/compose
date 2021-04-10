from context import *


def _import_helper(name: str, attr: str):
    try:
        module = __import__(f'services.{name}.helper', fromlist=[attr])
        return getattr(module, attr)
    except:
        return None


def eusure_dependency(config: Config, name: str):
    logger = config.logger

    # find program name
    program = _import_helper(name, 'DEPENDENCY_PROGRAM') or name

    # find installer script
    with open(f'./services/{name}/install.sh') as f:
        script = '\n'.join(f.readlines())

    logger.info(f'Checking installation: {name}')
    for node, outputs in config.command_all(f'which {program}'):
        if not outputs:
            logger.info(f'Installing {name} on {node}')
            config.command(node, script,
                           install_name=name, install_program=program)


def eusure_dependencies(config: Config):
    for name in config.collect_dependencies():
        eusure_dependency(config, name)


def compose_cluster(config: Config):
    for node, outputs in config.command_all(f'which {program}'):
        pass


def install_core(config: Config):
    eusure_dependencies(config)
    compose_cluster(config)
