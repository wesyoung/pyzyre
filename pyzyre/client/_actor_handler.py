import logging
import os
import uuid

from czmq import Zmsg

TRACE_EVASIVE = os.getenv('ZYRE_EVASITVE_TRACE')
TRACE = os.getenv('ZYRE_TRACE')

logger = logging.getLogger('pyzyre.client')


class AppHandler(object):
    def __init__(self, node, peers):
        self.node = node
        self.peers = peers

        assert node

    def on_join(self, message):
        group = message.popstr().decode('utf-8')
        logger.debug('joining %s' % group)
        self.node.join(group)

    def on_whisper(self, message):
        address = message.popstr().decode('utf-8')
        msg = message.popstr().decode('utf-8')
        m = Zmsg()
        m.addstr(msg)
        address = self.peers[str(address)]
        address = uuid.UUID(address).hex.upper()
        self.node.whisper(address, m)

    def on_shout(self, message):
        g = message.popstr()
        msg = message.popstr()
        logger.debug('shouting[%s]: %s' % (g.decode('utf-8'), msg))
        self.node.shouts(g, msg)

    def on_leave(self, message):
        g = message.popstr()
        logger.debug('leaving: %s' % g)
        self.node.leave(g.encode('utf-8'))


class NetworkHandler(object):

    def __init__(self, pipe, node, args, peers):
        self.pipe = pipe
        self.node = node
        self.args = args
        self.peers = peers
        self.peer_first = None

        assert pipe
        assert args
        assert node

    def on_evasive(self, e):
        if TRACE or TRACE_EVASIVE:
            logger.debug('EVASIVE {}'.format(e.peer_name()))

        self.pipe.send_multipart(['EVASIVE'.encode('utf-8'), e.peer_name()])

    def on_enter(self, e):
        logger.debug('ENTER {} - {}'.format(e.peer_name(), e.peer_uuid()))

        self.peers[e.peer_name()] = e.peer_uuid()
        if not self.peer_first:
            self.peer_first = e.peer_name()  # this should be the gossip node

        self.pipe.send_multipart(['ENTER'.encode('utf-8'), e.peer_uuid(), e.peer_name()])

    def on_join(self, e):
        logger.debug('JOIN [{}] [{}]'.format(e.group(), e.peer_name()))
        self.pipe.send_multipart(['JOIN'.encode('utf-8'), e.peer_name(), e.group()])

    def on_leave(self, e):
        logger.debug('LEAVE [{}] [{}]'.format(e.group(), e.peer_name()))
        self.pipe.send_multipart(['LEAVE'.encode('utf-8'), e.peer_name(), e.group()])

    def on_shout(self, e):
        m = e.get_msg().popstr()
        logger.debug('SHOUT [{}] [{}]: {} - {}'.format(e.group(), e.peer_name(), e.peer_uuid(), m))
        self.pipe.send_multipart(['SHOUT'.encode('utf-8'), e.group(), e.peer_name(), e.peer_uuid(), m])

    def on_whisper(self, e):
        m = e.get_msg().popstr()
        logger.debug('WHISPER [{}]: {}'.format(e.peer_name(), m))
        self.pipe.send_multipart(['WHISPER'.encode('utf-8'), e.peer_name(), e.peer_uuid(), m])

    def on_exit(self, e):
        logger.debug('EXIT [{}] [{}]'.format(e.group(), e.peer_name()))

        # remove the peer from gossip
        if e.peer_uuid() != self.node.uuid():
            self.node.gossip_unpublish(e.peer_uuid())

        if e.peer_name() in self.peers:
            del self.peers[e.peer_name()]
            if self.args.get('gossip_connect') and (len(self.peers) == 0 or e.peer_name() == self.peer_first):
                logger.debug('lost connection to gossip node, reconnecting...')

                if self.args.get('gossip_publickey'):
                    self.node.gossip_connect_curve(self.args['gossip_publickey'], self.args['gossip_connect'])
                else:
                    self.node.gossip_connect(self.args['gossip_connect'])

        self.pipe.send_multipart(['EXIT'.encode('utf-8'), e.peer_name(), str(len(self.peers)).encode('utf-8')])
