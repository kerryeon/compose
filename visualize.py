#!/usr/bin/python3

import sys

from context import import_helper


if __name__ == '__main__':
    type = str(sys.argv[1])
    visualizer = import_helper(type, 'visualize')
    visualizer()
