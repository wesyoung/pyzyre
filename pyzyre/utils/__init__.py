import os.path
from argparse import ArgumentParser
import logging
from .znetwork import *

from czmq import Zcert

from pyzyre.constants import VERSION, ENDPOINT, PUBLIC_KEY, GOSSIP_PUBLIC_KEY, SECRET_KEY, CURVE_ALLOW_ANY, ZYRE_GROUP, \
    NODE_NAME, CERT_PATH, LOG_FORMAT, LOGLEVEL, GOSSIP_BIND, GOSSIP_CONNECT

if not os.path.exists(CERT_PATH):
    CERT_PATH = None


logger = logging.getLogger(__name__)


def get_argument_parser(advanced=True):
    BasicArgs = ArgumentParser(add_help=False)
    BasicArgs.add_argument('-d', '--debug', action="store_true")
    BasicArgs.add_argument('-v', '--verbose', action="store_true")
    BasicArgs.add_argument('-V', '--version', action="version", version=VERSION)

    if not advanced:
        return ArgumentParser(parents=[BasicArgs], add_help=False)

    BasicArgs.add_argument('-i', '--interface', help='specify zsys_interface for beacon')
    BasicArgs.add_argument('-l', '--endpoint', help='specify ip listening endpoint [default %(default)s]',
                           default=ENDPOINT)
    BasicArgs.add_argument('--advertised-endpoint', help='[GOSSIP ONLY] advertise an alternative endpoint (NAT)')

    BasicArgs.add_argument('--name', help='specify node name [default %(default)s]', default=NODE_NAME)
    BasicArgs.add_argument('--group', default=ZYRE_GROUP)

    BasicArgs.add_argument('--cert', help="specify local cert path")
    BasicArgs.add_argument('--curve', help="enable CURVE (TLS)", action="store_true")
    BasicArgs.add_argument('--publickey', help="specify CURVE public key [default %(default)s]", default=PUBLIC_KEY)
    BasicArgs.add_argument('--secretkey', help="specify CURVE secret key [default %(default)s]", default=SECRET_KEY)

    BasicArgs.add_argument('--gossip-bind', help='bind gossip endpoint on this node [default %(default)s]',
                           default=GOSSIP_BIND)
    BasicArgs.add_argument('--gossip-connect', help='connect to gossip endpoint [default %(default)s]',
                           default=GOSSIP_CONNECT)

    BasicArgs.add_argument('--gossip-cert', help="specify gossip cert path [default %(default)s]", default=CERT_PATH)
    BasicArgs.add_argument('--gossip-publickey', help='specify CURVE public key [default %(default)s]',
                           default=GOSSIP_PUBLIC_KEY)
    BasicArgs.add_argument('--zauth-curve-allow', help="specify zauth curve allow [default %(default)s]",
                           default=CURVE_ALLOW_ANY)

    return ArgumentParser(parents=[BasicArgs], add_help=False)


def setup_logging(args):
    loglevel = logging.getLevelName(LOGLEVEL)

    if args.verbose:
        loglevel = logging.INFO

    if args.debug:
        loglevel = logging.DEBUG

    console = logging.StreamHandler()
    logging.getLogger('').setLevel(loglevel)
    console.setFormatter(logging.Formatter(LOG_FORMAT))
    logging.getLogger('').addHandler(console)


def setup_curve(args):
    if not args.curve and not args.publickey and not args.cert and not args.gossip_publickey and not args.gossip_cert:
        return None

    if args.cert:
        cert = Zcert.load(args.cert)
        logger.info('CURVE configured via CERT...')
        return cert

    if args.curve or args.publickey or args.gossip_publickey:
        cert = Zcert()
        if args.publickey:
            if not args.secretkey:
                raise SystemExit

            cert = Zcert.new_from_txt(args.publickey, args.secretkey)

    if args.gossip_cert:
        gcert = Zcert.load(args.gossip_cert)
        args.gossip_publickey = gcert.public_txt()
        if not args.gossip_connect:
            args.gossip_connect = (gcert.meta('gossip-endpoint'))

        if not cert:
            cert = Zcert()

    logger.info('CURVE configured...')
    return cert



