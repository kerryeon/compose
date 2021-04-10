#!/usr/bin/python3

import yaml

from context import Config
import service


def main(path: str):
    with open(path) as f:
        contexts = yaml.load_all(f, Loader=yaml.SafeLoader)
    for context in contexts:
        service.solve(Config.load(path, context))


if __name__ == '__main__':
    main('./batch.yaml')
