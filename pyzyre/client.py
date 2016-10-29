import zmq
import logging
from time import sleep
from czmq import Zactor, zactor_fn, create_string_buffer
import os
from pyzyre.utils import resolve_gossip, resolve_endpoint
import names
from pprint import pprint

GOSSIP_PORT = '49154'
SERVICE_PORT = '49155'
GOSSIP_ENDPOINT = 'zyre.local'
GOSSIP_REMOTE = 'tcp://{}:{}'.format(GOSSIP_ENDPOINT, GOSSIP_PORT)
CHANNEL = 'ZYRE'

logger = logging.getLogger(__name__)


class Client(object):

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.stop_zyre()
        return self

    def __init__(self, task=None, **kwargs):

        # disable CZMQ from capturing SIGINT
        os.environ['ZSYS_SIGHANDLER'] = 'false'

        self.channel = kwargs.get('channel', 'ZYRE')
        self.interface = kwargs.get('iface')

        self.parent_loop = kwargs.get('loop')

        self.gossip_bind = kwargs.get('gossip_bind')
        self.beacon = kwargs.get('beacon')
        self.gossip_connect = kwargs.get('gossip_connect')
        self.endpoint = kwargs.get('endpoint')
        self.name = kwargs.get('name', names.get_full_name())
        self.actor = None
        self.task = zactor_fn(task)

        self._init_zyre()

    def _init_zyre(self):
        # setup czmq/zyre

        if self.beacon:
            if self.interface:
                os.environ["ZSYS_INTERFACE"] = self.interface
        else:
            if self.gossip_bind:
                self.gossip_bind = resolve_gossip(GOSSIP_PORT, self.gossip_bind)
                logger.info('gossip-bind: %s' % self.gossip_bind)
            else:
                self.gossip_connect = resolve_gossip(GOSSIP_PORT, self.gossip_connect)
                logger.info('gossip-connect: %s' % self.gossip_connect)

            if not self.endpoint:
                self.endpoint = resolve_endpoint(SERVICE_PORT, interface=self.interface)

        actor_args = [
            'channel=%s' % self.channel,
            'name=%s' % self.name,
        ]

        if self.gossip_bind:
            actor_args.append('gossip_bind=%s' % self.gossip_bind)
        elif self.gossip_connect:
            actor_args.append('gossip_connect=%s' % self.gossip_connect)
        else:
            actor_args.append('beacon=1')

        if self.endpoint:
            actor_args.append('endpoint=%s' % self.endpoint)

        pprint(actor_args)
        actor_args = ','.join(actor_args)
        self.actor_args = create_string_buffer(actor_args)

        self.actor = None
        self._actor = None

    def start_zyre(self):
        # this starts the actor
        # since this is a fork, it needs to stay out of the way
        # if we try to re-cast it with zmq, things hang.
        self._actor = Zactor(self.task, self.actor_args)
        self.actor = zmq.Socket(shadow=self._actor.resolve(self._actor).value)

    def stop_zyre(self):
        self.actor.send_multipart(['$$STOP', ''.encode('utf-8')])
        sleep(0.1)  # cleanup

    def send_message(self, msg):
        self.actor.send_multipart([msg.encode('utf-8')])