from argparse import ArgumentParser
import zmq
import logging
from czmq import Zactor, zactor_fn, create_string_buffer, Zcert
import os
import os.path
from pyzyre.utils import resolve_gossip, resolve_endpoint
import names
from pprint import pprint
from ._client_task import task as client_task
import sys
from zmq.eventloop import ioloop
from time import sleep
from pyzyre.constants import GOSSIP_PORT, SERVICE_PORT, ZYRE_GROUP, LOG_FORMAT, PYVERSION, GOSSIP_CONNECT, ENDPOINT

NODE_NAME = os.getenv('ZYRE_NODE_NAME')

logger = logging.getLogger(__name__)


class DefaultHandler(object):
    def on_shout(self, client, group, peer, address, message):
        pass

    def on_whisper(self, client, peer, message):
        pass

    def on_enter(self, client, peer):
        pass

    def on_join(self, client, peer, group):
        pass

    def on_leave(self, client, peer, group):
        pass

    def on_exit(self, client, peer):
        pass


class Client(object):

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if self.actor:
            self.stop_zyre()
        return self

    def __init__(self, handler=DefaultHandler(), **kwargs):

        # disable CZMQ from capturing SIGINT
        os.environ['ZSYS_SIGHANDLER'] = 'false'

        self.handler = handler

        self.group = kwargs.get('group', ZYRE_GROUP)
        self._groups = self.group.split(',')
        self.group = '|'.join(self.group.split(','))
        self.interface = kwargs.get('interface') or '*'

        self.parent_loop = kwargs.get('loop')
        self.gossip_bind = kwargs.get('gossip_bind')
        self.beacon = kwargs.get('beacon')
        self.gossip_connect = kwargs.get('gossip_connect', GOSSIP_CONNECT)
        self.endpoint = kwargs.get('endpoint', ENDPOINT)
        self.cert = kwargs.get('cert')
        self.gossip_publickey = kwargs.get('gossip_publickey')

        self.name = kwargs.get('name', NODE_NAME)
        if not self.name:
            self.name = '{}_{}'.format(names.get_first_name().lower(), names.get_last_name().lower())

        self.actor = None
        self.task = zactor_fn(client_task)
        self.verbose = kwargs.get('verbose')

        if self.gossip_bind:
            self.beacon = False

        elif self.gossip_connect:
            self.beacon = False

        else:
            self.endpoint = False
            self.beacon = True

        self._init_zyre()

    def _init_beacon(self):
        logger.debug(self.interface)
        os.environ["ZSYS_INTERFACE"] = self.interface

    def _init_gossip_bind(self):
        # is gossip_bind an interface?
        if len(self.gossip_bind) <= 5:
            # we need this to resolve the endpoint
            self.interface = self.gossip_bind
            if not self.endpoint:
                self.endpoint = resolve_endpoint(SERVICE_PORT, interface=self.interface)

        self.gossip_bind = resolve_gossip(GOSSIP_PORT, self.gossip_bind)
        logger.debug('gossip-bind: %s' % self.gossip_bind)
        logger.debug("ENDPOINT: %s" % self.endpoint)

        if not self.endpoint:
            if self.interface:
                self.endpoint = resolve_endpoint(SERVICE_PORT, interface=self.interface)
            else:
                raise RuntimeError('A local interface must be specified')

    def _init_gossip_connect(self):
        try:
            logger.info('resolving gossip-connect: {}'.format(self.gossip_connect))
            self.gossip_connect = resolve_gossip(GOSSIP_PORT, self.gossip_connect)
            logger.debug('gossip-connect: %s' % self.gossip_connect)

        except RuntimeError as e:
            logger.error(e)
            logger.debug('falling back to beacon mode..')
            self.beacon = 1
            self.gossip_connect = None

        if not self.endpoint:
            if self.interface:
                self.endpoint = resolve_endpoint(SERVICE_PORT, interface=self.interface)
            else:
                raise RuntimeError('A local interface must be specified')

    def _init_zyre(self):
        # setup czmq/zyre
        # disable CZMQ from capturing SIGINT
        os.environ['ZSYS_SIGHANDLER'] = 'false'

        if self.gossip_bind:
            self._init_gossip_bind()

        if self.gossip_connect:
            self._init_gossip_connect()

        if self.beacon:
            self._init_beacon()

        actor_args = [
            'group=%s' % self.group,
            'name=%s' % self.name,
        ]

        if self.verbose:
            actor_args.append('verbose=1')

        if self.gossip_bind:
            actor_args.append('gossip_bind=%s' % self.gossip_bind)

        elif self.gossip_connect:
            actor_args.append('gossip_connect=%s' % self.gossip_connect)

        else:
            actor_args.append('beacon=1')

        if self.endpoint:
            actor_args.append('endpoint=%s' % self.endpoint)

        if self.cert:
            actor_args.append('publickey=%s' % self.cert.public_txt())
            actor_args.append('secretkey=%s' % self.cert.secret_txt())

        if self.gossip_publickey:
            actor_args.append('gossip_publickey=%s' % self.gossip_publickey)

        actor_args = ','.join(actor_args)
        self.actor_args = create_string_buffer(actor_args)

        self.actor = None
        self._actor = None

    def start_zyre(self):
        self._actor = Zactor(self.task, self.actor_args)
        self.actor = zmq.Socket(shadow=self._actor.resolve(self._actor).value)

    def stop_zyre(self):
        self.actor.send_multipart(['$$STOP'.encode('utf-8')])
        m = self.actor.recv_multipart()
        sleep(0.01)
        del self._actor

    def join(self, group):
        logger.debug('sending join')
        self.actor.send_multipart(['JOIN', group.encode('utf-8')])

    def shout(self, group, message):
        if isinstance(message, str):
            message = message.decode('utf-8')
        self.actor.send_multipart(['SHOUT', group.encode('utf-8'), message.encode('utf-8')])

    def whisper(self, message, address):
        logger.debug('sending whisper to %s' % address)
        if isinstance(message, str):
            message = message.decode('utf-8')
        self.actor.send_multipart(['WHISPER', address, message.encode('utf-8')])
        logger.debug('message sent via whisper')

    # deprecate
    def send_message(self, message, group=None, address=None):
        if isinstance(message, str) and PYVERSION == 2:
            message = unicode(message, 'utf-8')

        if address:
            logger.debug('sending whisper to %s' % address)
            self.actor.send_multipart(['WHISPER', address, message.encode('utf-8')])
            logger.debug('message sent via whisper')
        else:
            if not group:
                group = self._groups[0]
            self.actor.send_multipart(['SHOUT', group.encode('utf-8'), message.encode('utf-8')])

    def handle_message(self, s, e):
        m = s.recv_multipart()

        m_type = m.pop(0)

        if m_type == 'SHOUT':
            group, peer, address, message = m
            self.handler.on_shout(self, group, peer, address, message)

        elif m_type == 'ENTER':
            self.handler.on_enter(self, peer=m)

        elif m_type == 'WHISPER':
            peer, message = m
            self.handler.on_whisper(self, peer, message)

        elif m_type == 'EXIT':
            peer, peers_remining = m
            logger.debug(peers_remining)
            if self.gossip_connect and peers_remining == '0':
                self.parent_loop.remove_handler(self.actor)
                self.stop_zyre()
                self.start_zyre()
                self.parent_loop.add_handler(self.actor, self.handle_message, zmq.POLLIN)
            self.handler.on_exit(self, peer)

        elif m_type == 'JOIN':
            peer, group = m
            self.handler.on_join(self, peer, group)

        elif m_type == 'LEAVE':
            peer, group = m
            self.handler.on_leave(self, peer, group)

        else:
            logger.warn("unhandled m_type {} rest of message is {}".format(m_type, m))


def main():
    p = ArgumentParser()

    endpoint = resolve_endpoint(SERVICE_PORT)

    p.add_argument('--gossip-bind', help='bind gossip endpoint on this node')
    p.add_argument('--gossip-connect')
    p.add_argument('-i', '--interface', help='specify zsys_interface for beacon')
    p.add_argument('-l', '--endpoint', help='specify ip listening endpoint [default %(default)s]', default=endpoint)
    p.add_argument('-d', '--debug', help='enable debugging', action='store_true')

    p.add_argument('--curve', help="enable CURVE (TLS)", action="store_true")
    p.add_argument('--publickey', help="specify CURVE public key")
    p.add_argument('--secretkey', help="specify CURVE secret key")
    p.add_argument('--gossip-publickey')

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

    cert = None
    auth = None
    gossip_publickey = args.gossip_publickey

    if args.curve or args.publickey or args.gossip_publickey:
        from zmq.auth.thread import ThreadAuthenticator
        ctx = zmq.Context.instance()
        auth = ThreadAuthenticator(ctx, log=logger)
        auth.start()
        # Tell authenticator to use the certificate in a directory
        auth.configure_curve(domain='*', location=zmq.auth.CURVE_ALLOW_ANY)

        logger.debug('enabling curve...')
        cert = Zcert()
        if args.publickey:
            if not args.secretkey:
                logger.error("CURVE Secret Key required")
                raise SystemExit

            cert = Zcert.new_from_txt(args.publickey, args.secretkey)

    client = Client(
        group=args.group,
        loop=loop,
        gossip_bind=args.gossip_bind,
        gossip_connect=args.gossip_connect,
        endpoint=args.endpoint,
        verbose=verbose,
        interface=args.interface,
        cert=cert,
        gossip_publickey=gossip_publickey
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

    if auth:
        auth.stop()

if __name__ == '__main__':
    main()
