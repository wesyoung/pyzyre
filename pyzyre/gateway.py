from argparse import ArgumentParser
import zmq
import logging
from pyzyre.utils import resolve_endpoint
from zmq.eventloop import ioloop
from pyzyre.constants import SERVICE_PORT, ZYRE_GROUP, LOG_FORMAT
from pyzyre.client import Client, DefaultHandler


logger = logging.getLogger(__name__)


class GatewayHandler(DefaultHandler):
    def __init__(self, pub):
        self.pub = pub

    def on_shout(self, client, group, peer, address, message):
        self.pub.send_multipart([group, message])


# see examples/pub.py and sub.py
def main():
    p = ArgumentParser()

    endpoint = resolve_endpoint(SERVICE_PORT)

    p.add_argument('--gossip-bind', help='bind gossip endpoint on this node')
    p.add_argument('--gossip-connect')
    p.add_argument('-i', '--interface', help='specify zsys_interface for beacon')
    p.add_argument('-l', '--endpoint', help='specify ip listening endpoint [default %(default)s]', default=endpoint)
    p.add_argument('-d', '--debug', help='enable debugging', action='store_true')
    p.add_argument('-p', '--pub', help='endpoint to bind for PUB socket [default %(default)s]', default="tcp://*:5001")
    p.add_argument('-u', '--pull', help='endpoint to bind for PULL socket [default %(default)s]', default="tcp://*:5002")

    p.add_argument('--group', default=ZYRE_GROUP)

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

    context = zmq.Context()
    pub = context.socket(zmq.PUB)
    if not args.pub.startswith(('tcp://', 'udp://', 'ipc://')):
        args.pub = 'tcp://%s' % args.pub

    logger.info('listing for PUB on %s' % args.pub)
    pub.bind(args.pub)

    pull = context.socket(zmq.PULL)
    if not args.pull.startswith(('tcp://', 'udp://', 'ipc://')):
        args.pull = 'tcp://%s' % args.pull

    logger.info('listing for PULL on %s' % args.pull)
    pull.bind(args.pull)

    client = Client(
        handler=GatewayHandler(pub),
        group=args.group,
        loop=loop,
        gossip_bind=args.gossip_bind,
        gossip_connect=args.gossip_connect,
        endpoint=args.endpoint,
        verbose=verbose,
        interface=args.interface,
    )

    def handle_pull(*args):
        req = pull.recv_multipart()
        cmd = req[0]
        args = req[1:]
        if cmd == 'PUB':
            client.shout(*args)
            pub.send_multipart(args)
        elif cmd == 'SUB':
            client.join(*args)

    client.start_zyre()
    loop.add_handler(client.actor, client.handle_message, zmq.POLLIN)
    loop.add_handler(pull, handle_pull, zmq.POLLIN)

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
