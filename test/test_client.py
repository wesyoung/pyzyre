import sys
import pytest
from zmq.eventloop import ioloop
from pyzyre.client import Client
from pyzyre._client_task import task
import netifaces as ni

from time import sleep
from pprint import pprint
import zmq

ioloop.install()

@pytest.fixture
def iface():
    if sys.platform == 'darwin':
        return 'en0'
    else:
        if 'eth0' in ni.interfaces():
            return 'eth0'
        else:
            return ni.interfaces()[1]


def test_client_beacon(iface):
    # test with multi-process framework..
    c1 = Client(task=task, verbose='1')
    c1.start_zyre()

    c2 = Client(task=task, verbose='1')
    c2.start_zyre()

    sleep(0.01)

    loop = ioloop.IOLoop.instance()
    loop.add_handler(c1.actor, c1.handle_message, zmq.POLLIN)

    def test_fcn():
        c2.shout('ZYRE', 'TEST')
        sleep(1)

    loop.run_sync(test_fcn)

    c1.stop_zyre()
    c2.stop_zyre()

    loop.remove_handler(c1.actor)

    # cleanup
    sleep(1)


def test_client_gossip(iface):
    # test with multi-process framework..
    c1 = Client(task=task, verbose='1', gossip_bind='ipc:///tmp/gossip.ipc', endpoint='ipc:///tmp/c1.ipc')
    c1.start_zyre()

    c2 = Client(task=task, verbose='1', gossip_connect='ipc:///tmp/gossip.ipc', endpoint='ipc:///tmp/c2.ipc')
    c2.start_zyre()

    sleep(0.01)

    loop = ioloop.IOLoop.instance()
    loop.add_handler(c1.actor, c1.handle_message, zmq.POLLIN)

    def test_fcn():
        c2.shout('ZYRE', 'TEST')
        sleep(1)

    loop.run_sync(test_fcn)

    c1.stop_zyre()
    c2.stop_zyre()

    loop.remove_handler(c1.actor)

    # cleanup
    sleep(1)