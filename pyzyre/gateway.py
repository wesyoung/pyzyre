from argparse import ArgumentParser
import zmq
import logging
from pyzyre.utils import resolve_endpoint
from zmq.eventloop import ioloop
from pyzyre.constants import SERVICE_PORT, ZYRE_GROUP, LOG_FORMAT, CURVE_ALLOW_ANY, GOSSIP_PUBLIC_KEY, PUBLIC_KEY, \
    SECRET_KEY
from pyzyre.client import Client, DefaultHandler
from czmq import Zcert


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

    p.add_argument('--gossip-cert', help="specify gossip cert path")
    p.add_argument('--cert', help="specify local cert path")
    p.add_argument('--curve', help="enable CURVE (TLS)", action="store_true")
    p.add_argument('--publickey', help="specify CURVE public key [default %(default)s]", default=PUBLIC_KEY)
    p.add_argument('--secretkey', help="specify CURVE secret key [default %(default)s]", default=SECRET_KEY)
    p.add_argument('--zauth-curve-allow', help="specify zauth curve allow [default %(default)s]",
                   default=CURVE_ALLOW_ANY)

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
        logger.debug("Loadded")
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
        verbose=verbose,
        interface=args.interface,
        cert=cert,
        gossip_publickey=gossip_publickey,
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
