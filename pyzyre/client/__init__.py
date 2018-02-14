import logging
import os
import os.path
from time import sleep
import names
from pprint import pprint
import re

import zmq
from czmq import Zactor, zactor_fn, create_string_buffer, lib

from ._task import task as client_task
from ..utils import resolve_endpoint
from pyzyre.constants import GOSSIP_PORT, SERVICE_PORT, ZYRE_GROUP, GOSSIP_CONNECT, ENDPOINT, CURVE_ALLOW_ANY, \
    NODE_NAME, DefaultHandler

ZAUTH_TRACE = os.getenv('ZAUTH_TRACE', False)

logger = logging.getLogger(__name__)


class Client(object):

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
        self.first_node = None
        self.zauth = kwargs.get('zauth_curve_allow')
        self.advertised_endpoint = kwargs.get('advertised_endpoint')

        self.name = kwargs.get('name', NODE_NAME)
        if not self.name:
            self.name = '{}_{}'.format(names.get_first_name().lower(), names.get_last_name().lower())

        self.actor = None
        self.task = zactor_fn(client_task)

        if self.gossip_bind:
            self.beacon = False
            self.gossip_connect = False

        elif self.gossip_connect:
            self.beacon = False

        else:
            self.endpoint = False
            self.beacon = True

        if isinstance(self.zauth, str):
            self.zauth = self._zauth(self.zauth)

        self._init_zyre()

    def _zauth(self, allow=CURVE_ALLOW_ANY):
        logger.debug("spinning up zauth..")

        zauth = Zactor(zactor_fn(lib.zauth), None)

        if ZAUTH_TRACE:
            logger.debug('turning on auth verbose')
            lib.zstr_sendx(zauth, "VERBOSE", None)
            zauth.sock().wait()

        if allow:
            logger.debug("configuring Zauth...")
            lib.zstr_sendx(zauth, "CURVE", allow, None)
            zauth.sock().wait()

        logger.debug('Zauth complete')

        return zauth

    def _init_gossip_connect(self):
        try:
            logger.debug('resolving gossip-connect: {}'.format(self.gossip_connect))
            self.gossip_connect = resolve_endpoint(self.gossip_connect, GOSSIP_PORT)

        except RuntimeError as e:
            logger.error(e)
            logger.debug('falling back to beacon mode..')
            self.beacon = 1
            self.gossip_connect = None

        self.endpoint = resolve_endpoint(self.endpoint, SERVICE_PORT)

    def _init_gossip_bind(self):
        self.gossip_bind = resolve_endpoint(self.gossip_bind, GOSSIP_PORT)
        self.endpoint = resolve_endpoint(self.endpoint, SERVICE_PORT)

    def _init_zyre(self):
        # setup czmq/zyre
        # disable CZMQ from capturing SIGINT
        os.environ['ZSYS_SIGHANDLER'] = 'false'

        if self.gossip_bind:
            self._init_gossip_bind()

        if self.gossip_connect:
            self._init_gossip_connect()

        if self.beacon:
            os.environ["ZSYS_INTERFACE"] = self.interface

        actor_args = [
            'group=%s' % self.group,
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

        if self.advertised_endpoint:
            actor_args.append('advertised_endpoint=%s' % self.advertised_endpoint)

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

        if self.zauth:
            del self.zauth  # destroy old actor
            self.zauth = None  # re-establish attrib

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

    def leave(self, group):
        logger.debug('sending LEAVE for %s' % group)
        self.actor.send_multipart(['LEAVE', group])

    def handle_message(self, s, e):
        m = s.recv_multipart()

        m_type = m.pop(0)

        if m_type == 'SHOUT':
            group, peer, address, message = m
            self.handler.on_shout(self, group, peer, address, message)

        elif m_type == 'ENTER':
            # set teh first node name in case we need it later (gossip)
            if not self.first_node and self.gossip_connect:
                self.first_node = m[1]

            self.handler.on_enter(self, peer=m)

        elif m_type == 'WHISPER':
            peer, message = m
            self.handler.on_whisper(self, peer, message)

        elif m_type == 'EXIT':
            peer, peers_remining = m
            self.handler.on_exit(self, peer)

        elif m_type == 'JOIN':
            peer, group = m
            self.handler.on_join(self, peer, group)

        elif m_type == 'LEAVE':
            peer, group = m
            self.handler.on_leave(self, peer, group)

        elif m_type == 'EVASIVE':
            peer = m
            self.handler.on_evasive(self, peer)

        else:
            logger.warn("unhandled m_type {} rest of message is {}".format(m_type, m))


