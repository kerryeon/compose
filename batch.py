#!/usr/bin/python3

import yaml

from context import Config
from settings import Settings


def main(config: str, settings: str, verbose: bool):
    with open(config) as f:
        context = yaml.load(f, Loader=yaml.SafeLoader)
    with open(settings) as f:
        settings_context = yaml.load(f, Loader=yaml.SafeLoader)
        
    # FIXME: implement manual GPT partitioning
    # - sudo sgdisk /dev/some-partition -E = Total number of blocks
    # - sudo sgdisk /dev/some-partition -n 1:                         2048:{1 * Total / osdsPerNode}
    # - sudo sgdisk /dev/some-partition -n 2:{   1  * Total / osdsPerNode}:{2 * Total / osdsPerNode} ...
    # - sudo sgdisk /dev/some-partition -n n:{(n-1) * Total / osdsPerNode}:{n * Total / osdsPerNode}
    # - [outputs]: /dev/some-partitionp1 ... /dev/some-partitionpn
    # - wipe filesystem on each partition: **reuse** from the used one!
    # - [each partition] sudo dd of=/dev/some-partitionpx if=/dev/zero bs=1M count=100 && sync
    exit(1)

    config = Config.load(config, context)
    settings = Settings.load(settings, settings_context, config)
    settings.solve(verbose=verbose)


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
    args = parser.parse_args()

    main(args.file, args.settings, args.verbose)
