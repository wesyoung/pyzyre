from argparse import ArgumentParser
import zmq
import logging
from pyzyre.utils import resolve_endpoint
from zmq.eventloop import ioloop
from pyzyre.constants import SERVICE_PORT, ZYRE_GROUP, LOG_FORMAT, GOSSIP_PORT
from pyzyre.client import Client, DefaultHandler


logger = logging.getLogger(__name__)


class BrokerHandler(DefaultHandler):
    def on_shout(self, client, group, peer, address, message):
        logger.info('SHOUT[{}][{}]: {}'.format(group, peer, message))


# see examples/pub.py and sub.py
def main():
    p = ArgumentParser()

    endpoint = resolve_endpoint(SERVICE_PORT)
    gossip = resolve_endpoint(GOSSIP_PORT)

    p.add_argument('-g','--gossip-bind', help='bind gossip endpoint on this node [default %(default)s]', default=gossip)
    p.add_argument('-e', '--endpoint', help='specify ip listening endpoint [default %(default)s]', default=endpoint)
    p.add_argument('-d', '--debug', help='enable debugging', action='store_true')

    p.add_argument('--group', help="group to join [default %(default)s]", default=ZYRE_GROUP)

    args = p.parse_args()

    loglevel = logging.INFO
    if args.debug:
        loglevel = logging.DEBUG

    console = logging.StreamHandler()
    logging.getLogger('').setLevel(loglevel)
    console.setFormatter(logging.Formatter(LOG_FORMAT))
    logging.getLogger('').addHandler(console)
    logging.propagate = False

    ioloop.install()
    loop = ioloop.IOLoop.instance()

    client = Client(
        handler=BrokerHandler(),
        group=args.group,
        loop=loop,
        gossip_bind=args.gossip_bind,
        endpoint=args.endpoint,
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
