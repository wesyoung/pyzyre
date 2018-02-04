from argparse import ArgumentParser, RawDescriptionHelpFormatter
import textwrap
import zmq
import logging
from czmq import Zcert
from pyzyre.utils import resolve_endpoint
import sys
from zmq.eventloop import ioloop
from pyzyre.constants import SERVICE_PORT, LOG_FORMAT
from .client import Client

from .utils import get_argument_parser, setup_logging

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

    endpoint = resolve_endpoint(SERVICE_PORT)

    args = p.parse_args()

    setup_logging(args, name=__name__)

    ioloop.install()
    loop = ioloop.IOLoop.instance()

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

    client = Client(
        group=args.group,
        loop=loop,
        gossip_bind=args.gossip_bind,
        gossip_connect=args.gossip_connect,
        endpoint=args.endpoint,
        interface=args.interface,
        cert=cert,
        gossip_publickey=args.gossip_publickey,
        zauth=args.zauth_curve_allow,
        name=args.name
    )

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
