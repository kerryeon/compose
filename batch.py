#!/usr/bin/python3

import yaml

from context import Config
import service


def main(path: str):
    with open(path) as f:
        contexts = list(yaml.load_all(f, Loader=yaml.SafeLoader))

    index = 0
    for context in contexts:
        if not isinstance(context, dict):
            continue
        service.solve(Config.load(f'[{index}] {path}', context))
        index += 1
        print()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='Automatic cluster batch benchmarking tool for GIST NetAI Lab.',
    )
    parser.add_argument(
        '-f', '--file', metavar='FILENAME', type=str,
        default='./batch.yaml',
        help='a configuration file',
    )
    args = parser.parse_args()

    main(args.file)
