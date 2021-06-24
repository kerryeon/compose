#!/usr/bin/python3

import yaml

from context import Config
from settings import Settings


def main(config: str, settings: str):
    with open(config) as f:
        context = yaml.load(f, Loader=yaml.SafeLoader)
    with open(settings) as f:
        settings_context = yaml.load(f, Loader=yaml.SafeLoader)

    config = Config.load(config, context)
    settings = Settings.load(settings, settings_context, config)
    settings.solve()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='Automatic cluster batch benchmarking tool for GIST NetAI Lab.',
    )
    parser.add_argument(
        '-f', '--file', metavar='FILENAME', type=str,
        default='./config.yaml',
        help='a configuration file',
    )
    parser.add_argument(
        '-s', '--settings', metavar='FILENAME', type=str,
        default='./settings.yaml',
        help='a settings file',
    )
    args = parser.parse_args()

    main(args.file, args.settings)
