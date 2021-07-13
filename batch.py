#!/usr/bin/python3

import yaml

from context import Config
from settings import Settings


def main(config: str, settings: str, verbose: bool, reuse: bool):
    with open(config) as f:
        context = yaml.load(f, Loader=yaml.SafeLoader)
    with open(settings) as f:
        settings_context = yaml.load(f, Loader=yaml.SafeLoader)

    config = Config.load(config, context)
    settings = Settings.load(settings, settings_context, config)
    settings.solve(verbose=verbose, reuse=reuse)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='Automatic cluster batch benchmarking tool for GIST NetAI Lab.',
    )
    parser.add_argument(
        '-f', '--file', metavar='FILENAME', type=str,
        default='./config.yaml',
        help='A configuration file.',
    )
    parser.add_argument(
        '-s', '--settings', metavar='FILENAME', type=str,
        default='./settings.yaml',
        help='A settings file.',
    )
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='Whether to show logs.',
    )
    parser.add_argument(
        '--reuse', action='store_true',
        help='Whether to reuse the existing cluster. Unstable but fast.',
    )
    args = parser.parse_args()

    main(args.file, args.settings, args.verbose, args.reuse)
