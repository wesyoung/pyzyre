import logging
import textwrap
from argparse import ArgumentParser, RawDescriptionHelpFormatter
import os

import zmq
import zmq.auth
from .client import Client, DefaultHandler
from zmq.eventloop import ioloop
from .utils import get_argument_parser, setup_logging, setup_curve
from .constants import NODE_NAME

CERT_PATH = os.getenv('ZYRE_CERT_PATH', os.path.expanduser('~/.curve'))
SECRET_KEY_PATH = os.getenv('ZYRE_CERT_PATH', os.path.expanduser('~/.curve/broker.key_secret'))

logger = logging.getLogger(__name__)


class BrokerHandler(DefaultHandler):
    def on_shout(self, client, group, peer, address, message):
        logger.info('SHOUT[{}][{}]: {}'.format(group, peer, message))


# see examples/pub.py and sub.py
def main():
    p = get_argument_parser()
    p = ArgumentParser(
        description=textwrap.dedent('''\
                example usage:
                    $ zyre-broker -d
                    $ zyre-broker --curve
                '''),
        formatter_class=RawDescriptionHelpFormatter,
        prog='zyre-broker',
        parents=[p]
    )

    args = p.parse_args()

    setup_logging(args)

    if not NODE_NAME:
        args.name = 'broker'

    if os.path.exists(SECRET_KEY_PATH):
        public, secret = zmq.auth.load_certificate(SECRET_KEY_PATH)
        if not secret:
            raise("Error loading keys: %" % SECRET_KEY_PATH)

        args.gossip_publickey = public
        args.publickey = public
        args.secretkey = secret
        args.curve = True

    args.cert = setup_curve(args)

    ioloop.install()
    loop = ioloop.IOLoop.instance()

    client = Client(
        handler=BrokerHandler(),
        loop=loop,
        **args.__dict__
    )

    client.start_zyre()
    loop.add_handler(client.actor, client.handle_message, zmq.POLLIN)

    terminated = False
    while not terminated:
        try:
            logger.info('starting loop...')
            loop.start()

        except KeyboardInterrupt:
            logger.info('SIGINT Received')
            terminated = True

        except Exception as e:
            terminated = True
            logger.error(e)

    logger.info('shutting down..')

    client.stop_zyre()


if __name__ == '__main__':
    main()
