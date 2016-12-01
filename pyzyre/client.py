import zmq
import logging
from czmq import Zactor, zactor_fn, create_string_buffer
import os
import os.path
from pyzyre.utils import resolve_gossip, resolve_endpoint
import names
from pprint import pprint
from time import sleep
from pyzyre.constants import GOSSIP_PORT, SERVICE_PORT, ZYRE_GROUP, LOG_FORMAT, PYVERSION

logger = logging.getLogger(__name__)


class Client(object):

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if self.actor:
            self.stop_zyre()
        return self

    def __init__(self, task=None, **kwargs):

        # disable CZMQ from capturing SIGINT
        os.environ['ZSYS_SIGHANDLER'] = 'false'

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
        self.task = zactor_fn(task)
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
