import zmq
import logging
from argparse import ArgumentParser
from zmq.eventloop import ioloop
from pyzyre.utils import resolve_endpoint
from pyzyre.client import Client
from pyzyre.chat import task as chat_task
from pprint import pprint

ioloop.install()

GOSSIP_PORT = '49154'
SERVICE_PORT = '49155'
GOSSIP_ENDPOINT = 'zyre.local'
GOSSIP_REMOTE = 'tcp://{}:{}'.format(GOSSIP_ENDPOINT, GOSSIP_PORT)
CHANNEL = 'ZYRE'

logger = logging.getLogger(__name__)


def handle_message(s, e):
    m = s.recv()
    logger.info(m)

if __name__ == '__main__':
    p = ArgumentParser()

    endpoint = resolve_endpoint(SERVICE_PORT)

    p.add_argument('--gossip-bind', help='bind gossip endpoint on this node')
    p.add_argument('--gossip-connect')
    p.add_argument('--beacon', help='use beacon instead of gossip', action='store_true')
    p.add_argument('--beacon-listener', help='run in listening-only mode', action='store_true')
    p.add_argument('-i', '--interface', help='specify zsys_interface for beacon')
    p.add_argument('-l', '--endpoint', help='specify ip listening endpoint [default %(default)s]', default=endpoint)

    p.add_argument('--channel', default=CHANNEL)

    args = p.parse_args()

    # Create a StreamHandler for debugging
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
    logger.propagate = False

    if args.gossip_bind:
        loop = ioloop.IOLoop.instance()
        if args.interface and (resolve_endpoint(SERVICE_PORT) == args.endpoint):
            endpoint = None

        with Client(task=chat_task, channel=args.channel, loop=loop, gossip_bind=args.gossip_bind, endpoint=endpoint,
                    iface=args.interface) as client:
            client.start_zyre()
            loop.add_handler(client.actor, handle_message, zmq.POLLIN)

            try:
                loop.start()
            except KeyboardInterrupt:
                logger.info('SIGINT Received')
            except Exception as e:
                logger.error(e)

    elif args.beacon_listener:
        with Client(task=chat_task, iface=args.interface, channel=args.channel, m_handler_cb=handle_message,
                    beacon=args.beacon) as client:

            client.start_zyre()
            loop = ioloop.IOLoop.instance()
            loop.add_handler(client.actor, handle_message, zmq.POLLIN)

            try:
                loop.start()
            except KeyboardInterrupt:
                logger.info('SIGINT Received')
            except Exception as e:
                logger.error(e)
    else:
        if args.gossip_connect and (resolve_endpoint(SERVICE_PORT) == args.endpoint):
            endpoint = None

        if args.interface and (resolve_endpoint(SERVICE_PORT) == args.endpoint):
            endpoint = None

        with Client(task=chat_task, iface=args.interface, channel=args.channel, m_handler_cb=handle_message,
                    beacon=args.beacon, gossip_connect=args.gossip_connect, endpoint=endpoint) as client:

            client.start_zyre()

            logger.info('client started...')

            try:
                while True:
                    msg = raw_input('message to send: ')
                    client.send_message(msg)
            except KeyboardInterrupt:
                logger.info('SIGINT Received')
            except Exception as e:
                logger.error(e)
