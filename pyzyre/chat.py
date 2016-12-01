from zyre import Zyre, ZyreEvent
import zmq
import logging
from czmq import Zsock, string_at, Zmsg
import names
import uuid
import sys
from zmq.eventloop import ioloop
from argparse import ArgumentParser
from pyzyre.client import Client
from pyzyre.utils import resolve_endpoint
from pyzyre.constants import ZYRE_GROUP, LOG_FORMAT, SERVICE_PORT
import os
from pyzyre import color

logger = logging.getLogger('')

EVASIVE_TIMEOUT = os.environ.get('ZYRE_EVASIVE_TIMEOUT', 5000)  # zyre defaults
EXPIRED_TIMEOUT = os.environ.get('ZYRE_EXPIRED_TIMEOUT', 30000)


def task(pipe, arg):
    args = string_at(arg)
    args = dict(item.split("=") for item in args.split(","))

    name = args.get('name', names.get_full_name())
    group = args.get('group', ZYRE_GROUP)
    verbose = args.get('verbose')

    logger.info('setting up node: %s' % name)
    n = Zyre(name)

    logger.debug('setting evasive timeout: {}'.format(EVASIVE_TIMEOUT))
    n.set_evasive_timeout(int(EVASIVE_TIMEOUT))

    logger.debug('setting experation timer: {}'.format(EXPIRED_TIMEOUT))
    n.set_expired_timeout(int(EXPIRED_TIMEOUT))

    if verbose == '1':
        logger.info('setting verbose...')
        logger.setLevel(logging.DEBUG)
        n.set_verbose()

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
    while not terminated:
        items = dict(poller.poll())

        try:
            if pipe_s in items and items[pipe_s] == zmq.POLLIN:
                message = Zmsg.recv(pipe)

                if not message:
                    break  # SIGINT

                msg_type = message.popstr().decode('utf-8')

                # message to quit
                if msg_type == "$$STOP":
                    terminated = True
                elif msg_type == '$$ID':
                    pipe_s.send_string(n.uuid().decode('utf-8'))
                else:
                    if msg_type == 'whisper':
                        address = message.popstr().decode('utf-8')
                        msg = message.popstr().decode('utf-8')
                        m = Zmsg()
                        m.addstr(msg)
                        address = peers[str(address)]
                        address = uuid.UUID(address).hex.upper()
                        n.whisper(address, m)
                    else:
                        msg = message.popstr().decode('utf-8')
                        n.shouts(group[0], msg.encode('utf-8'))

            elif ss in items and items[ss] == zmq.POLLIN:
                e = ZyreEvent(n)

                msg_type = e.type().decode('utf-8')
                logger.debug('found ZyreEvent: %s' % msg_type)
                #logger.debug(e.get_msg().popstr())

                if msg_type == "ENTER":
                    logger.debug('ENTER {} - {}'.format(e.peer_name(), e.peer_uuid()))
                    peers[e.peer_name()] = e.peer_uuid()
                    pipe_s.send_multipart(['ENTER', e.peer_uuid(), e.peer_name()])
                    #headers = e.headers() # zlist

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
                    pipe_s.send_multipart(['EXIT', str(len(peers))])

                elif msg_type == 'EVASIVE':
                    logger.debug('EVASIVE {}'.format(e.peer_name()))

                else:
                    logger.warn('unknown message type: {}'.format(msg_type))
        except Exception as e:
            import traceback
            print traceback.print_exc()
            logger.error(e)

    logger.info('shutting down...')
    n.stop()


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
        task=task
    )

    def on_stdin(s, e):
        content = s.readline()

        if content.startswith('CLIENT:'):
            address, message = content.split(' - ')
            address = address.split(':')[1]
            client.send_message(message, address=address)
        else:
            client.send_message(content.encode('utf-8'))

    def handle_message(s, e):
        m = s.recv_multipart()

        logger.debug(m)

        m_type = m.pop(0)

        logger.info(m_type)

        if m_type == 'ENTER':
            logger.info("ENTER {}".format(m))

        elif m_type == 'WHISPER':
            peer, message = m
            logger.info('[WHISPER:{}] {}'.format(peer, message))
        elif m_type == 'SHOUT':
            group, peer, address, message = m
            logger.info('[SHOUT:{}][{}]: {}'.format(group, peer, message))
        elif m_type == 'EXIT':
            peers_remining = m[0]
            logger.debug(peers_remining)
            if args.gossip_connect and peers_remining == '0':
                loop.remove_handler(client.actor)
                client.stop_zyre()
                client.start_zyre()
                loop.add_handler(client.actor, handle_message, zmq.POLLIN)
        else:
            logger.warn("unhandled m_type {} rest of message is {}".format(m_type, m))

    client.start_zyre()

    loop.add_handler(client.actor, handle_message, zmq.POLLIN)
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
