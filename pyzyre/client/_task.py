import logging
import os

import zmq
from czmq import Zsock, string_at, Zmsg, Zcert
from pyzyre.constants import ZYRE_GROUP
from zyre import Zyre, ZyreEvent

logger = logging.getLogger(__name__)

EVASIVE_TIMEOUT = os.environ.get('ZYRE_EVASIVE_TIMEOUT', 5000)  # zyre defaults
EXPIRED_TIMEOUT = os.environ.get('ZYRE_EXPIRED_TIMEOUT', '15000')
EXPIRED_TIMEOUT = int(EXPIRED_TIMEOUT)
TRACE_EVASIVE = os.getenv('ZYRE_EVASITVE_TRACE')
NODE_NAME = os.getenv('ZYRE_NODE_NAME')
TRACE = os.getenv('ZYRE_TRACE')


def task(pipe, arg):
    args = string_at(arg).decode('utf-8')
    args = dict(item.split("=", 1) for item in args.split(","))

    name = args.get('name')
    if not name:
        raise RuntimeError('missing node name')

    group = args.get('group', ZYRE_GROUP)

    logger.debug('setting up node: %s' % name)
    n = Zyre(name.encode('utf-8'))

    logger.debug('setting evasive timeout: {}'.format(EVASIVE_TIMEOUT))
    n.set_evasive_timeout(int(EVASIVE_TIMEOUT))

    logger.debug('setting experation timer: {}'.format(EXPIRED_TIMEOUT))
    n.set_expired_timeout(EXPIRED_TIMEOUT)

    if TRACE:
        logger.info('setting verbose...')
        logger.setLevel(logging.DEBUG)
        n.set_verbose()

    if args.get('publickey'):
        cert = Zcert.new_from_txt(args['publickey'].encode('utf-8'), args['secretkey'].encode('utf-8'))
        n.set_zcert(cert)

    if args.get('advertised_endpoint'):
        logger.debug('setting advertised_endpoint: %s' % args['advertised_endpoint'])
        n.set_advertised_endpoint(args['advertised_endpoint'].encode('utf-8'))

    if args.get('endpoint'):
        logger.debug('setting endpoint: {}'.format(args['endpoint']))
        if n.set_endpoint(args['endpoint'].encode('utf-8')) == -1:
            logger.error('unable to bind endpoint: %s')
            logger.warn('endpoint will be auto generated using tcp://*:*')

    if not args.get('beacon'):
        logger.debug('setting up gossip')

        if args.get('gossip_bind'):
            logger.debug('binding gossip: {}'.format(args['gossip_bind']))
            n.gossip_bind(args['gossip_bind'].encode('utf-8'))
        else:
            logger.debug('connecting to gossip group: {}'.format(args['gossip_connect']))
            if args.get('gossip_publickey'):
                n.gossip_connect_curve(args['gossip_publickey'].encode('utf-8'), args['gossip_connect'].encode('utf-8'))
            else:
                n.gossip_connect(args['gossip_connect'].encode('utf-8'))

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

    logger.debug('staring node...')
    n.start()

    group = group.split('|')
    for g in group:
        logger.debug('joining: %s' % g)
        n.join(g.encode('utf-8'))

    pipe_zsock_s.signal(0)  # OK

    peers = {}
    terminated = False
    # TODO- catch SIGINT

    from ._actor_handler import NetworkHandler, AppHandler
    handle = NetworkHandler(pipe_s, n, args, peers)
    app_handler = AppHandler(n, peers)

    while not terminated:
        items = dict(poller.poll())

        try:
            # from the application to the network
            if pipe_s in items and items[pipe_s] == zmq.POLLIN:
                message = Zmsg.recv(pipe)

                if not message:
                    break  # SIGINT

                msg_type = message.popstr().decode('utf-8').upper()

                # message to quit
                if msg_type == "$$STOP":
                    for g in group:
                        n.leave(g.encode('utf-8'))
                    terminated = True

                elif msg_type == '$$ID':
                    pipe_s.send_string(n.uuid().decode('utf-8'))

                elif msg_type in ['WHISPER', 'JOIN', 'SHOUT', 'LEAVE']:
                    h = getattr(app_handler, 'on_' + msg_type.lower())
                    h(message)

                else:
                    logger.warn('unknown message type: {}'.format(msg_type))

            # from network to the application
            elif ss in items and items[ss] == zmq.POLLIN:
                e = ZyreEvent(n)

                msg_type = e.type().decode('utf-8').upper()

                if msg_type in ['ENTER', 'EXIT', 'LEAVE', 'JOIN', 'SHOUT', 'WHISPER', 'EVASIVE']:
                    h = getattr(handle, 'on_' + msg_type.lower())
                    h(e)

                else:
                    logger.warn('unknown message type: {}'.format(msg_type))

        except Exception as e:
            logger.exception("Unhandled exception in main io loop")

    logger.debug('shutting down node')
    n.stop()

    logger.debug('done')
