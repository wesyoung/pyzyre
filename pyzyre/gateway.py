from argparse import ArgumentParser, RawDescriptionHelpFormatter
import textwrap
import logging

import zmq
from zmq.eventloop import ioloop
from czmq import Zcert

from .utils import resolve_endpoint, setup_logging, get_argument_parser
from .constants import SERVICE_PORT
from .client import Client, DefaultHandler

logger = logging.getLogger('')


class GatewayHandler(DefaultHandler):
    def __init__(self, pub):
        self.pub = pub

    def on_shout(self, client, group, peer, address, message):
        self.pub.send_multipart([group, message])


# see examples/pub.py and sub.py
def main():
    p = get_argument_parser()
    p = ArgumentParser(
        description=textwrap.dedent('''\
                example usage:
                    $ zyre-gateway -d
                '''),
        formatter_class=RawDescriptionHelpFormatter,
        prog='zyre-gateway',
        parents=[p]
    )

    endpoint = resolve_endpoint(SERVICE_PORT)

    p.add_argument('-p', '--pub', help='endpoint to bind for PUB socket [default %(default)s]',
                   default="tcp://*:5001")
    p.add_argument('-u', '--pull', help='endpoint to bind for PULL socket [default %(default)s]',
                   default="tcp://*:5002")

    args = p.parse_args()

    setup_logging(args)

    cert = None

    if args.curve or args.publickey or args.cert or args.gossip_publickey:
        logger.debug('enabling curve...')
        cert = Zcert()
        if args.publickey:
            if not args.secretkey:
                logger.error("CURVE Secret Key required")
                raise SystemExit

            cert = Zcert.new_from_txt(args.publickey, args.secretkey)

        if args.cert:
            cert = Zcert.load(args.cert)

        logger.debug("Public Key: %s" % cert.public_txt())
        logger.debug("Secret Key: %s" % cert.secret_txt())

    if args.gossip_cert:
        gcert = Zcert.load(args.gossip_cert)
        args.gossip_publickey = gcert.public_txt()
        if not args.gossip_connect:
            args.gossip_connect = (gcert.meta('gossip-endpoint'))

        if not cert:
            cert = Zcert()

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
        #verbose=verbose,
        interface=args.interface,
        cert=cert,
        gossip_publickey=args.gossip_publickey,
        zauth=args.zauth_curve_allow
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
