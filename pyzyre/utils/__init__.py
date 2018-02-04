import netifaces as ni
import netaddr
import os.path
import socket
from argparse import ArgumentParser
import logging

from czmq import Zcert

from pyzyre.constants import VERSION, ENDPOINT, PUBLIC_KEY, GOSSIP_PUBLIC_KEY, SECRET_KEY, CURVE_ALLOW_ANY, ZYRE_GROUP, \
    NODE_NAME, CERT_PATH, LOG_FORMAT, LOGLEVEL

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

    BasicArgs.add_argument('--name', help='specify node name [default %(default)s]', default=NODE_NAME)
    BasicArgs.add_argument('--group', default=ZYRE_GROUP)

    BasicArgs.add_argument('--cert', help="specify local cert path")
    BasicArgs.add_argument('--curve', help="enable CURVE (TLS)", action="store_true")
    BasicArgs.add_argument('--publickey', help="specify CURVE public key [default %(default)s]", default=PUBLIC_KEY)
    BasicArgs.add_argument('--secretkey', help="specify CURVE secret key [default %(default)s]", default=SECRET_KEY)

    BasicArgs.add_argument('--gossip-bind', help='bind gossip endpoint on this node')
    BasicArgs.add_argument('--gossip-connect')

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
    if not args.curve or args.publickey or args.cert or args.gossip_publickey or args.gossip_cert:
        return None

    if args.curve or args.publickey or args.cert or args.gossip_publickey:
        cert = Zcert()
        if args.publickey:
            if not args.secretkey:
                raise SystemExit

            cert = Zcert.new_from_txt(args.publickey, args.secretkey)

        if args.cert:
            cert = Zcert.load(args.cert)

    if args.gossip_cert:
        gcert = Zcert.load(args.gossip_cert)
        args.gossip_publickey = gcert.public_txt()
        if not args.gossip_connect:
            args.gossip_connect = (gcert.meta('gossip-endpoint'))

        if not cert:
            cert = Zcert()

    logger.info('CURVE configured...')
    return cert


def resolve_interface(address):
    address = netaddr.IPAddress(address)

    for i in ni.interfaces():
        ii = ni.ifaddresses(i)
        if not ii.get(ni.AF_INET):
            continue

        ii = ii[ni.AF_INET]
        ii = netaddr.IPNetwork('{}/{}'.format(ii[0]['addr'], ii[0]['netmask']))
        try:
            if address in ii:
                return i
        except AttributeError:
            pass


def resolve_address(i):
    return interface_to_address(i)


def interface_to_address(i):
    i = ni.ifaddresses(i)
    i = i[ni.AF_INET]
    i = i[0]['addr']
    return i


def default_address():
    i = default_interface()
    return interface_to_address(i)


def default_interface():
    try:
        return ni.gateways()['default'][ni.gateways()['default'].keys()[0]][1]
    except IndexError:
        raise RuntimeError("Unable to determine endpoint address")


def resolve_endpoint(port, address=None, interface=None):
    endpoint = address

    if address:
        if address.startswith(('ipc://', 'tcp://', 'udp://')):
            return address

        try:
            # is it an ip address?
            socket.inet_aton(address)
        except socket.error:
            try:
                # is it an FQDN?
                socket.gethostbyname(address)
            except socket.error:
                if os.path.basename(address):
                    return 'ipc://{}'.format(address)

        if 'tcp://' not in address:
            endpoint = 'tcp://%s' % address

        if port not in address:
            endpoint = '{}:{}'.format(endpoint, port)

        return endpoint

    if interface and interface != '*':
        i = interface_to_address(interface)
        endpoint = 'tcp://{}:{}'.format(i, port)
        return endpoint

    endpoint = default_address()
    endpoint = 'tcp://{}:{}'.format(endpoint, port)

    return endpoint


def resolve_gossip(port, address=None):
    if not address:
        address = resolve_endpoint(port)
    elif len(address) <= 5:
        # they sent us an interface...
        address = resolve_endpoint(port, interface=address)
    else:
        address = resolve_endpoint(port, address)

    return address


def resolve_gossip_bootstrap(server):
    import dns
    if ":" in server:
        server = server.split(":")[0]

    r = dns.resolver.query(server, 'TXT')
    if len(r) == 0:
        return False

    return r[0].strings[0]
