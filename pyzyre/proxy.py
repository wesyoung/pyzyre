from zyre import Zyre, ZyreEvent
import zmq
import logging
from czmq import Zsock, string_at, Zmsg
import names
import uuid
import sys
from zmq.eventloop import ioloop
from argparse import ArgumentParser
from pyzyre.client import Client
from pyzyre.chat import task
import zmq
from pyzyre.utils import resolve_endpoint
from pyzyre.constants import ZYRE_CHANNEL, LOG_FORMAT, SERVICE_PORT
import os
from pyzyre import color

logger = logging.getLogger('')

EVASIVE_TIMEOUT = os.environ.get('ZYRE_EVASIVE_TIMEOUT', 5000)  # zyre defaults
EXPIRED_TIMEOUT = os.environ.get('ZYRE_EXPIRED_TIMEOUT', 30000)


def main():
    p = ArgumentParser()
    p.add_argument('-d', '--debug', help='enable debugging', action='store_true')

    p.add_argument('-i', '--interface', help='specify zsys_interface for beacon')
    p.add_argument('--channel', default=ZYRE_CHANNEL)
    p.add_argument('--bind', default='ipc:///tmp/zyre.ipc')

    args = p.parse_args()

    loglevel = logging.INFO
    verbose = False
    if args.debug:
        loglevel = logging.DEBUG
        verbose = '1'

    console = logging.StreamHandler()
    logging.getLogger('').setLevel(loglevel)
    console.setFormatter(logging.Formatter(LOG_FORMAT))
    logging.getLogger('').addHandler(console)
    logging.propagate = False

    ioloop.install()
    loop = ioloop.IOLoop.instance()

    zyre = Client(
        channel=args.channel,
        loop=loop,
        verbose=verbose,
        interface=args.interface,
        task=task
    )

    def handle_message(s, e):
        m = s.recv_multipart()

        logger.debug(m)

        zyre.send_message(m[0].encode('utf-8'))

    zyre.start_zyre()

    ctx = zmq.Context()
    s = ctx.socket(zmq.PULL)
    s.bind(args.bind)

    loop.add_handler(s, handle_message, zmq.POLLIN)

    try:
        loop.start()
    except KeyboardInterrupt:
        logger.info('SIGINT Received')
    except Exception as e:
        logger.error(e)

    zyre.stop_zyre()

if __name__ == '__main__':
    main()
