#!/usr/bin/python3

import yaml

import service
from context import Config


def main(config: str):
    with open(config) as f:
        context = yaml.load(f, Loader=yaml.SafeLoader)
    service.solve(Config.load(config, context))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='Automatic cluster configuration & benchmarking tool for GIST NetAI Lab.',
    )
    parser.add_argument(
        '-f', '--file', metavar='FILENAME', type=str,
        default='./config.yaml',
        help='a configuration file',
    )
    args = parser.parse_args()

    main(args.file)
