from context import *

DEPENDENCY_PROGRAM = 'dummy-program'


def collect_dependencies(service: Service) -> set:
    return set()


def compose(config: Config, desc: Service):
    config.logger.info(f'service name: {desc.name}')
