import logging
from zmq.eventloop import ioloop
from argparse import ArgumentParser
import zmq
from pyzyre.constants import ZYRE_CHANNEL, LOG_FORMAT
from csirtg_indicator import Indicator
import sys

logger = logging.getLogger(__name__)


def main():
    p = ArgumentParser()

    p.add_argument('-d', '--debug', help='enable debugging', action='store_true')

    p.add_argument('-i')

    args = p.parse_args()

    loglevel = logging.INFO
    if args.debug:
        loglevel = logging.DEBUG

    console = logging.StreamHandler()
    logging.getLogger('').setLevel(loglevel)
    console.setFormatter(logging.Formatter(LOG_FORMAT))
    logging.getLogger('').addHandler(console)
    logging.propagate = False

    ctx = zmq.Context()
    z = ctx.socket(zmq.PUSH)
    z.connect('ipc:///tmp/zyre.ipc')

    def on_stdin(s, e):
        content = s.readline().strip("\n")
        i = Indicator(content.decode("utf-8"))
        logger.info('sending: {}'.format(i))
        z.send_multipart([str(i).encode('utf-8')])

    if args.i:
        i = Indicator(args.i)
        logger.info('sending {}'.format(i))
        z.send_multipart([str(i).encode('utf-8')])
    else:
        ioloop.install()
        loop = ioloop.IOLoop.instance()

        loop.add_handler(sys.stdin, on_stdin, ioloop.IOLoop.READ)

        try:
            loop.start()
        except KeyboardInterrupt:
            logger.info('SIGINT Received')
        except Exception as e:
            logger.error(e)


if __name__ == '__main__':
    main()
