import logging
from zmq.eventloop import ioloop
from argparse import ArgumentParser
from pyzyre.client import Client
from pyzyre.chat import task
import zmq
from pyzyre.constants import ZYRE_GROUP, LOG_FORMAT, SERVICE_PORT, PYVERSION
import os
import select
import sys
from pprint import pprint
from pyzyre import color

logger = logging.getLogger('')


def main():
    p = ArgumentParser()
    p.add_argument('-d', '--debug', help='enable debugging', action='store_true')

    p.add_argument('-i', '--interface', help='specify zsys_interface for beacon')
    p.add_argument('--group', default=ZYRE_GROUP)
    p.add_argument('--address', default='ipc:///tmp/zyre.ipc')

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

    if select.select([sys.stdin, ], [], [], 0.0)[0]:
        ctx = zmq.Context()
        s = ctx.socket(zmq.PUSH)
        s.setsockopt(zmq.LINGER, 0)
        s.connect(args.address)

        content = sys.stdin.read().strip('\n')

        if PYVERSION == 2:
            content = unicode(content, encoding='utf-8', errors='ignore')

        logger.info('sending..')
        s.send_multipart([content.encode('utf-8')])
        logger.info('sent...')
        s.close()
    else:
        logger.info('running proxy..')
        ioloop.install()
        loop = ioloop.IOLoop.instance()

        zyre = Client(
            group=args.group,
            loop=loop,
            verbose=verbose,
            interface=args.interface,
            task=task
        )

        def handle_message(s, e):
            m = s.recv_multipart()

            logger.debug(m)

            zyre.send_message(m[0])

        zyre.start_zyre()

        ctx = zmq.Context()
        s = ctx.socket(zmq.PULL)
        s.bind(args.address)

        loop.add_handler(s, handle_message, zmq.POLLIN)

        try:
            loop.start()
        except KeyboardInterrupt:
            logger.info('SIGINT Received')
        except Exception as e:
            logger.error(e)

        zyre.stop_zyre()

    logger.info('done')

if __name__ == '__main__':
    main()
