import logging
import textwrap
from argparse import ArgumentParser, RawDescriptionHelpFormatter

import zmq
from .client import Client, DefaultHandler
from zmq.eventloop import ioloop
from .utils import get_argument_parser, setup_logging, setup_curve

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
