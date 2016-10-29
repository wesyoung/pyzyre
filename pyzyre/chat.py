from zyre import Zyre, ZyreEvent
import zmq
import logging
from czmq import Zactor, Zsock, zactor_fn, create_string_buffer, string_at, Zmsg, Zloop, zloop_reader_fn, Zproc
from zmq.eventloop import ioloop
import names
import uuid

ioloop.install()

GOSSIP_PORT = '49154'
SERVICE_PORT = '49155'
GOSSIP_ENDPOINT = 'zyre.local'
GOSSIP_REMOTE = 'tcp://{}:{}'.format(GOSSIP_ENDPOINT, GOSSIP_PORT)
CHANNEL = 'ZYRE'

logger = logging.getLogger('')


def task(pipe, arg):
    args = string_at(arg)
    args = dict(item.split("=") for item in args.split(","))

    name = args.get('name', names.get_full_name())
    chan = args.get('chan', CHANNEL)

    logger.info('setting up node: %s' % name)

    n = Zyre(name)
    n.set_verbose()

    if args.get('endpoint'):
        logger.info('setting endpoint: {}'.format(args['endpoint']))
        n.set_endpoint(args['endpoint'])

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

    n.start()
    n.join(chan)

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
                        logger.info('shouting {}'.format(msg))
                        n.shouts(chan, msg)
            elif ss in items and items[ss] == zmq.POLLIN:
                logger.info('found ZyreEvent')

                e = ZyreEvent(n)

                msg_type = e.type().decode('utf-8')

                logger.info(msg_type)

                if msg_type == 'JOIN':
                    logger.debug('JOIN [{}] [{}]'.format(e.group(), e.peer_name()))
                    pipe_s.send_multipart(['JOIN', e.peer_name(), e.group()])
                elif msg_type == 'EXIT':
                    logger.debug('EXIT [{}] [{}]'.format(e.group(), e.peer_name()))
                    del peers[e.peer_name()]
                    pipe_s.send_multipart(['EXIT', str(len(peers))])
                    # if peer name starts with 0000_ we need to signal a re-connect somehow
                elif msg_type == 'EVASIVE':
                    logger.debug('EVASIVE {}'.format(e.peer_name()))
                elif msg_type == "SHOUT":
                    m = e.get_msg().popstr()
                    logger.debug('SHOUT [{}] [{}]: {} - {}'.format(e.group(), e.peer_name(), e.peer_uuid(), m))
                    pipe_s.send_multipart(['SHOUT', e.group(), e.peer_name(), e.peer_uuid(), m])
                elif msg_type == "WHISPER":
                    m = e.get_msg().popstr()
                    logger.debug('WHISPER [{}]: {}'.format(e.peer_name(), m))
                    pipe_s.send_multipart(['WHISPER', e.peer_name(), e.peer_uuid(), m])
                elif msg_type == "ENTER":
                    logger.debug('ENTER {} - {}'.format(e.peer_name(), e.peer_uuid()))
                    peers[e.peer_name()] = e.peer_uuid()
                    pipe_s.send_multipart(['ENTER', e.peer_uuid(), e.peer_name()])
                    #headers = e.headers()

                else:
                    logger.warn('unknown message type: {}'.format(msg_type))
        except Exception as e:
            logger.error(e)

    logger.info('shutting down...')
    n.stop()

