import logging
import sys
import textwrap
from argparse import ArgumentParser, RawDescriptionHelpFormatter

import zmq
from pyzyre.client import Client
from zmq.eventloop import ioloop
from pyzyre.utils import get_argument_parser, setup_logging, setup_curve

logger = logging.getLogger('pyzyre.chat')


def main():
    p = get_argument_parser()
    p = ArgumentParser(
        description=textwrap.dedent('''\
            example usage:
                $ zyre-chat -d
            '''),
        formatter_class=RawDescriptionHelpFormatter,
        prog='zyre-chat',
        parents=[p]
    )

    args = p.parse_args()

    setup_logging(args)

    args.cert = setup_curve(args)

    ioloop.install()
    loop = ioloop.IOLoop.instance()

    client = Client(loop=loop, **args.__dict__)

    def on_stdin(s, e):
        content = s.readline().rstrip()

        if content.startswith('CLIENT:'):
            address, message = content.split(' - ')
            address = address.split(':')[1]
            client.whisper(message, address)
        else:
            client.shout(args.group, content.encode('utf-8'))

    client.start_zyre()

    loop.add_handler(client.actor, client.handle_message, zmq.POLLIN)
    loop.add_handler(sys.stdin, on_stdin, ioloop.IOLoop.READ)

    try:
        loop.start()
    except KeyboardInterrupt:
        logger.info('SIGINT Received')

    logger.info('shutting down..')

    client.stop_zyre()


if __name__ == '__main__':
    main()
