#!/usr/bin/python3

import yaml

from context import Config
import service


def main(path: str):
    with open(path) as f:
        context = yaml.load(f, Loader=yaml.SafeLoader)
    service.solve(Config.load(path, context))


if __name__ == '__main__':
    main('./config.yaml')
