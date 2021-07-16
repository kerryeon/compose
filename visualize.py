#!/usr/bin/python3

from context import import_helper


def main(mode: str, gui: bool):
    visualizer = import_helper(mode, 'visualize')
    visualizer(gui)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='A benchmark visualizing tool for GIST NetAI Lab.',
    )
    parser.add_argument(
        'mode', metavar='FILENAME', type=str,
        help='A benchmark type.',
    )
    parser.add_argument(
        '-g', '--gui', action='store_true',
        help='Visualize the results by GUI.',
    )
    args = parser.parse_args()

    main(args.mode, args.gui)
