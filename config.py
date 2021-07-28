#!/usr/bin/python3

import yaml

import service
from context import Config


def main(config: str, teardown: list[str], skip_benchmark: bool):
    with open(config) as f:
        context = yaml.load(f, Loader=yaml.SafeLoader)
    config = Config.load(config, context)

    if teardown is not None:
        service.teardown(config, teardown)
    else:
        service.solve(config, benchmark=not skip_benchmark)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='Automatic cluster configuration & benchmarking tool for GIST NetAI Lab.',
    )
    parser.add_argument(
        '-f', '--file', metavar='FILENAME', type=str,
        default='./config.yaml',
        help='A configuration file.',
    )
    parser.add_argument(
        '--teardown', metavar='NODE', type=str, nargs='+',
        help='Teardown a node and reboot.',
    )
    parser.add_argument(
        '--skip-benchmark', action='store_true',
        help='Skip the benchmark.',
    )
    args = parser.parse_args()

    main(args.file, args.teardown, args.skip_benchmark)
