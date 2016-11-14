import sys
import pytest
from zmq.eventloop import ioloop
from pyzyre.client import Client
from pyzyre.chat import task

from time import sleep
from pprint import pprint
import zmq

ioloop.install()


@pytest.fixture
def iface():
    if sys.platform == 'darwin':
        return 'en0'
    else:
        return 'eth0'


def _handle_message(s, e):
    m = s.recv_multipart()
    assert m
    print(m)


def test_client_beacon(iface):
    # test with multi-process framework..
    c1 = Client(task=task, verbose='1')
    c1.start_zyre()

    c2 = Client(task=task, verbose='1')
    c2.start_zyre()

    sleep(0.01)

    loop = ioloop.IOLoop.instance()
    loop.add_handler(c1.actor, _handle_message, zmq.POLLIN)

    def test_fcn():
        c2.send_message('TEST')
        sleep(2)

    loop.run_sync(test_fcn)

    c1.stop_zyre()
    c2.stop_zyre()


def test_client_gossip(iface):
    # test with multi-process framework..
    c1 = Client(task=task, verbose='1', gossip_bind='ipc:///tmp/gossip.ipc', endpoint='ipc:///tmp/c1.ipc')
    c1.start_zyre()

    c2 = Client(task=task, verbose='1', gossip_connect='ipc:///tmp/gossip.ipc', endpoint='ipc:///tmp/c2.ipc')
    c2.start_zyre()

    sleep(0.01)

    loop = ioloop.IOLoop.instance()
    loop.add_handler(c1.actor, _handle_message, zmq.POLLIN)

    def test_fcn():
        c2.send_message('TEST')
        sleep(2)

    loop.run_sync(test_fcn)

    c1.stop_zyre()
    c2.stop_zyre()
