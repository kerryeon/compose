from context import *

DEPENDENCY_PROGRAM = 'dummy-program'


def collect_dependencies(service: Service) -> set:
    return set()


def compose(config: Config, service: Service):
    config.logger.info(f'Initialize service: {service.name}')


def shutdown(config: Config, service: Service):
    config.logger.info(f'Doing shutdown: {service.name}')


def benchmark(config: Config, benchmark: Benchmark, name: str):
    config.logger.info(f'Finalizing benchmark: {name}')


def visualize(gui: bool):
    pass
