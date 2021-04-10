#!/usr/bin/python3


def init_logger():
    import logging
    import sys

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '[ %(levelname)s ] %(asctime)s -  %(message)s')
    handler.setFormatter(formatter)

    logger = logging.getLogger('compose')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    return logger


def main():
    from context import Config
    config = Config.load('./config.yaml', init_logger())

    import service
    service.solve(config)


if __name__ == '__main__':
    main()
