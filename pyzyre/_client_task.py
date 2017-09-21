from zyre import Zyre, ZyreEvent
import zmq
import logging
from czmq import Zsock, string_at, Zmsg, Zcert
import names
import uuid
from pyzyre.constants import ZYRE_GROUP
import os
from pprint import pprint
from pyzyre import color

logger = logging.getLogger('')

EVASIVE_TIMEOUT = os.environ.get('ZYRE_EVASIVE_TIMEOUT', 5000)  # zyre defaults
EXPIRED_TIMEOUT = os.environ.get('ZYRE_EXPIRED_TIMEOUT', 30000)
TRACE_EVASIVE = os.getenv('ZYRE_EVASITVE_TRACE')
NODE_NAME = os.getenv('ZYRE_NODE_NAME')
TRACE = os.getenv('ZYRE_TRACE')


def task(pipe, arg):
    args = string_at(arg)
    args = dict(item.split("=", 1) for item in args.split(","))

    name = args.get('name')
    if not name:
        raise RuntimeError('missing node name')

    group = args.get('group', ZYRE_GROUP)

    logger.info('setting up node: %s' % name)
    n = Zyre(name)

    logger.debug('setting evasive timeout: {}'.format(EVASIVE_TIMEOUT))
    n.set_evasive_timeout(int(EVASIVE_TIMEOUT))

    logger.debug('setting experation timer: {}'.format(EXPIRED_TIMEOUT))
    n.set_expired_timeout(int(EXPIRED_TIMEOUT))

    if TRACE:
        logger.info('setting verbose...')
        logger.setLevel(logging.DEBUG)
        n.set_verbose()

    if args.get('publickey'):
        cert = Zcert.new_from_txt(args['publickey'], args['secretkey'])
        n.set_zcert(cert)

    if args.get('endpoint'):
        logger.info('setting endpoint: {}'.format(args['endpoint']))
        n.set_endpoint(args['endpoint'])

    if not args.get('beacon'):
        logger.info('setting up gossip')
        if args.get('gossip_bind'):
            logger.info('binding gossip: {}'.format(args['gossip_bind']))
            n.gossip_bind(args['gossip_bind'])
        else:
            logger.info('connecting to gossip group: {}'.format(args['gossip_connect']))
            if args.get('gossip_publickey'):
                n.gossip_connect_curve(args['gossip_publickey'], args['gossip_connect'])
            else:
                n.gossip_connect(args['gossip_connect'])

    poller = zmq.Poller()

    pipe_zsock_s = Zsock(pipe, False)
    assert pipe_zsock_s

    pipe_s = zmq.Socket(shadow=pipe_zsock_s.resolve(pipe_zsock_s).value)
    assert pipe_s

    poller.register(pipe_s, zmq.POLLIN)

    # getting the zyre [czmq] socket
    # https://marc.info/?l=zeromq-dev&m=144719752222833&w=2
    s = n.socket()
    assert s

    # re-casting as native pyzmq socket
    ss = zmq.Socket(shadow=s.resolve(s).value)
    assert ss

    # registering
    poller.register(ss, zmq.POLLIN)

    logger.info('staring node...')
    n.start()

    group = group.split('|')
    for g in group:
        logger.info('joining: %s' % g)
        n.join(g)

    pipe_zsock_s.signal(0)  # OK

    peers = {}
    terminated = False
    # TODO- catch SIGINT
    while not terminated:
        items = dict(poller.poll())

        try:
            if pipe_s in items and items[pipe_s] == zmq.POLLIN:
                message = Zmsg.recv(pipe)

                if not message:
                    break  # SIGINT

                msg_type = message.popstr().decode('utf-8').upper()

                # message to quit
                if msg_type == "$$STOP":
                    for g in group:
                        n.leave(g)
                    terminated = True

                elif msg_type == '$$ID':
                    pipe_s.send_string(n.uuid().decode('utf-8'))

                elif msg_type == 'WHISPER':
                    address = message.popstr().decode('utf-8')
                    msg = message.popstr().decode('utf-8')
                    m = Zmsg()
                    m.addstr(msg)
                    address = peers[str(address)]
                    address = uuid.UUID(address).hex.upper()
                    n.whisper(address, m)

                elif msg_type == 'JOIN':
                    group = message.popstr().decode('utf-8')
                    logger.debug('joining %s' % group)
                    n.join(group)

                elif msg_type == 'SHOUT':
                    g = message.popstr()
                    msg = message.popstr()
                    logger.debug('shouting[%s]: %s' % (g, msg))
                    n.shouts(g, "%s", msg)

                else:
                    logger.warn('unknown message type: {}'.format(msg_type))

            elif ss in items and items[ss] == zmq.POLLIN:
                e = ZyreEvent(n)

                msg_type = e.type().decode('utf-8').upper()
                #logger.debug('found ZyreEvent: %s' % msg_type)
                #logger.debug(e.get_msg().popstr())

                if msg_type == "ENTER":
                    logger.debug('ENTER {} - {}'.format(e.peer_name(), e.peer_uuid()))
                    peers[e.peer_name()] = e.peer_uuid()
                    pipe_s.send_multipart(['ENTER', e.peer_uuid(), e.peer_name()])
                    #headers = e.headers() # zlist

                elif msg_type == 'LEAVE':
                    logger.debug('LEAVE [{}] [{}]'.format(e.group(), e.peer_name()))
                    pipe_s.send_multipart(['LEAVE', e.peer_name(), e.group()])

                elif msg_type == 'JOIN':
                    logger.debug('JOIN [{}] [{}]'.format(e.group(), e.peer_name()))
                    pipe_s.send_multipart(['JOIN', e.peer_name(), e.group()])

                elif msg_type == "SHOUT":
                    m = e.get_msg().popstr()
                    logger.debug('SHOUT [{}] [{}]: {} - {}'.format(e.group(), e.peer_name(), e.peer_uuid(), m))
                    pipe_s.send_multipart(['SHOUT', e.group(), e.peer_name(), e.peer_uuid(), m])

                elif msg_type == "WHISPER":
                    m = e.get_msg().popstr()
                    logger.debug('WHISPER [{}]: {}'.format(e.peer_name(), m))
                    pipe_s.send_multipart(['WHISPER', e.peer_name(), e.peer_uuid(), m])

                elif msg_type == 'EXIT':
                    logger.debug('EXIT [{}] [{}]'.format(e.group(), e.peer_name()))
                    if e.peer_name() in peers:
                        del peers[e.peer_name()]
                    pipe_s.send_multipart(['EXIT', e.peer_name(), str(len(peers))])

                elif msg_type == 'EVASIVE':
                    if TRACE or TRACE_EVASIVE:
                        logger.debug('EVASIVE {}'.format(e.peer_name()))

                else:
                    logger.warn('unknown message type: {}'.format(msg_type))
        except Exception as e:
            logger.exception("Unhandled exception in main io loop")

    logger.info('shutting down node')
    n.stop()

    logger.debug('done')