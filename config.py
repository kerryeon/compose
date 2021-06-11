#!/usr/bin/python3

import yaml

from context import Config
import service


def main(path: str):
    with open(path) as f:
        context = yaml.load(f, Loader=yaml.SafeLoader)
    service.solve(Config.load(path, context))


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
