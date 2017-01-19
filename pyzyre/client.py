from argparse import ArgumentParser
import zmq
import logging
from czmq import Zactor, zactor_fn, create_string_buffer
import os
import os.path
from pyzyre.utils import resolve_gossip, resolve_endpoint
import names
from pprint import pprint
from ._client_task import task as client_task
import sys
from zmq.eventloop import ioloop
from time import sleep
from pyzyre.constants import GOSSIP_PORT, SERVICE_PORT, ZYRE_GROUP, LOG_FORMAT, PYVERSION

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
        self.group = '|'.join(self.group.split(','))
        self.interface = kwargs.get('interface') or '*'

        self.parent_loop = kwargs.get('loop')
        self.gossip_bind = kwargs.get('gossip_bind')
        self.beacon = kwargs.get('beacon')
        self.gossip_connect = kwargs.get('gossip_connect')
        self.endpoint = kwargs.get('endpoint')
        self.name = kwargs.get('name', names.get_full_name())
        self.actor = None
        self.task = zactor_fn(client_task)
        self.verbose = kwargs.get('verbose')

        if self.gossip_bind:
            self.beacon = False
        elif self.gossip_connect:
            self.beacon = False
        else:
            self.beacon = True

        self._init_zyre()

    def _init_zyre(self):
        # setup czmq/zyre
        # disable CZMQ from capturing SIGINT
        os.environ['ZSYS_SIGHANDLER'] = 'false'

        # signal zbeacon in czmq
        if self.beacon:
            logger.debug(self.interface)
            os.environ["ZSYS_INTERFACE"] = self.interface
        else:
            if self.gossip_bind:
                # is gossip_bind an interface?
                if len(self.gossip_bind) <= 5:
                    # we need this to resolve the endpoint
                    self.interface = self.gossip_bind
                    if not self.endpoint:
                        self.endpoint = resolve_endpoint(SERVICE_PORT, interface=self.interface)

                self.gossip_bind = resolve_gossip(GOSSIP_PORT, self.gossip_bind)
                logger.debug('gossip-bind: %s' % self.gossip_bind)

            # gossip_connect
            else:
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

        actor_args = [
            'group=%s' % self.group,
            'name=%s' % self.name,
        ]

        if self.verbose or logger.getEffectiveLevel() == logging.DEBUG:
            actor_args.append('verbose=1')

        if self.gossip_bind:
            actor_args.append('gossip_bind=%s' % self.gossip_bind)
        elif self.gossip_connect:
            actor_args.append('gossip_connect=%s' % self.gossip_connect)
        else:
            actor_args.append('beacon=1')

        if self.endpoint:
            actor_args.append('endpoint=%s' % self.endpoint)

        actor_args = ','.join(actor_args)
        self.actor_args = create_string_buffer(actor_args)

        self.actor = None
        self._actor = None

    def start_zyre(self):
        self._actor = Zactor(self.task, self.actor_args)
        self.actor = zmq.Socket(shadow=self._actor.resolve(self._actor).value)

    def stop_zyre(self):
        self.actor.send_multipart(['$$STOP'])
        m = self.actor.recv_multipart()
        sleep(0.01)
        self.actor.close()
        del self._actor

    def join(self, group):
        logger.debug('sending join')
        self.actor.send_multipart(['join', group.encode('utf-8')])

    def shout(self, group, message):
        self.actor.send_multipart(['shout', group, message.encode('utf-8')])

    def send_message(self, message, address=None):
        if isinstance(message, str) and PYVERSION == 2:
            message = unicode(message, 'utf-8')

        if address:
            logger.debug('sending whisper to %s' % address)
            self.actor.send_multipart(['whisper', address, message.encode('utf-8')])
            logger.debug('message sent via whisper')
        else:
            self.actor.send_multipart(['shout', message.encode('utf-8')])
            #logger.debug('message sent via shout: {}'.format(message))

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

    client = Client(
        group=args.group,
        loop=loop,
        gossip_bind=args.gossip_bind,
        gossip_connect=args.gossip_connect,
        verbose=verbose,
        interface=args.interface,
    )

    def on_stdin(s, e):
        content = s.readline().rstrip()

        if content.startswith('CLIENT:'):
            address, message = content.split(' - ')
            address = address.split(':')[1]
            client.send_message(message, address=address)
        else:
            client.shout(args.group, content.encode('utf-8'))


    client.start_zyre()

    loop.add_handler(client.actor, client.handle_message, zmq.POLLIN)
    loop.add_handler(sys.stdin, on_stdin, ioloop.IOLoop.READ)

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
