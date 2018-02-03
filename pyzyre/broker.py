from argparse import ArgumentParser
import zmq
import logging
from pyzyre.utils import resolve_endpoint
from zmq.eventloop import ioloop
from pyzyre.constants import SERVICE_PORT, ZYRE_GROUP, LOG_FORMAT, GOSSIP_PORT, CURVE_ALLOW_ANY
from pyzyre.client import Client, DefaultHandler
from czmq import Zcert


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

    p.add_argument('--gossip-cert', help="specify gossip cert path")
    p.add_argument('--cert', help="specify local cert path")
    p.add_argument('--curve', help="enable CURVE (TLS)", action="store_true")
    p.add_argument('--publickey', help="specify CURVE public key [default %(default)s]", default=PUBLIC_KEY)
    p.add_argument('--secretkey', help="specify CURVE secret key [default %(default)s]", default=SECRET_KEY)
    
    p.add_argument('--zauth-curve-allow', help="specify zauth curve allow [default %(default)s]",
                   default=CURVE_ALLOW_ANY)

    args = p.parse_args()

    loglevel = logging.INFO
    if args.debug:
        loglevel = logging.DEBUG

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

    client = Client(
        handler=BrokerHandler(),
        group=args.group,
        loop=loop,
        gossip_bind=args.gossip_bind,
        endpoint=args.endpoint,
        cert=cert,
        gossip_publickey=gossip_publickey,
        zauth=args.zauth_curve_allow
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
