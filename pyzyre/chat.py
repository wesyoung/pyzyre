from zyre import Zyre, ZyreEvent
import zmq
import logging
from czmq import Zactor, Zsock, zactor_fn, create_string_buffer, string_at, Zmsg, Zloop, zloop_reader_fn, Zproc
from zmq.eventloop import ioloop

ioloop.install()

GOSSIP_PORT = '49154'
SERVICE_PORT = '49155'
GOSSIP_ENDPOINT = 'zyre.local'
GOSSIP_REMOTE = 'tcp://{}:{}'.format(GOSSIP_ENDPOINT, GOSSIP_PORT)
CHANNEL = 'ZYRE'

logger = logging.getLogger(__name__)


def task(pipe, arg):
    args = string_at(arg)
    args = dict(item.split("=") for item in args.split(","))

    name = args.get('name')
    chan = args.get('chan', CHANNEL)

    logger.info('setting up node: %s' % name)

    n = Zyre(name)
    n.set_verbose()
    from pprint import pprint

    pprint(args)
    if args.get('endpoint'):
        logger.info('setting endpoint: {}'.format(args['endpoint']))
        n.set_endpoint(args['endpoint'])

    if not args.get('beacon'):
        logger.info('setting up gossip')
        if args.get('gossip_bind'):
            n.gossip_bind(args['gossip_bind'])
        else:
            logger.info('connecting to gossip channel')
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

    n.start()
    n.join(chan)

    pipe_zsock_s.signal(0)  # OK

    terminated = False
    while not terminated:
        items = dict(poller.poll())

        if pipe_s in items and items[pipe_s] == zmq.POLLIN:
            message = Zmsg.recv(pipe)

            if not message:
                break  # SIGINT

            message = message.popstr().decode('utf-8')

            # message to quit
            if message == "$$STOP":
                terminated = True
            else:
                n.shouts(chan, message.decode('utf-8'))
        elif ss in items and items[ss] == zmq.POLLIN:
            logger.info('found ZyreEvent')

            e = ZyreEvent(n)

            msg_type = e.type().decode('utf-8')

            if msg_type == 'JOIN':
                logger.debug('JOIN [{}] [{}]'.format(e.group(), e.peer_name()))
            elif msg_type == 'EXIT':
                logger.debug('EXIT [{}] [{}]'.format(e.group(), e.peer_name()))
            elif msg_type == 'EVASIVE':
                logger.debug('EVASIVE {}'.format(e.peer_name()))
            elif msg_type == "SHOUT":
                m = e.get_msg().popstr()
                logger.debug('SHOUT [{}] [{}]: {}'.format(e.group(), e.peer_name(), m))
                pipe_s.send_multipart(['SHOUT', m])
            elif msg_type == "WHISPER":
                m = e.get_msg().popstr()
                logger.debug('WHISPER [{}]: {}'.format(e.peer_name(), m))
                pipe_s.send_multipart(['WHISPER', m])
            elif msg_type == "ENTER":
                headers = e.headers()
                #headers = json.loads(e.headers().decode('utf-8'))
                #logger.debug("NODE_MSG HEADERS: %s" % headers)

                #for key in headers:
                #    logger.debug("key = {0}, value = {1}".format(key, headers[key]))
            else:
                logger.warn('unknown message type: {}'.format(msg_type))

    logger.info('shutting down...')
    n.stop()
