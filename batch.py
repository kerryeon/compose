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
    main('./batch.yaml')
