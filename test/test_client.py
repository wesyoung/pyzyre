import sys
import pytest
from zmq.eventloop import ioloop
from pyzyre.client import Client
from pyzyre._client_task import task
from czmq import Zcert
import netifaces as ni

from time import sleep
from pprint import pprint
import zmq
import zmq.auth
from zmq.auth.thread import ThreadAuthenticator

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
    c1 = Client(interface=iface, task=task, verbose='1')
    c1.start_zyre()

    c2 = Client(interface=iface, task=task, verbose='1')
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
    sleep(2)


def test_client_beacon_curve(iface):
    ctx = zmq.Context.instance()
    auth = ThreadAuthenticator(ctx)
    auth.start()

    # Tell authenticator to use the certificate in a directory
    auth.configure_curve(domain='*', location=zmq.auth.CURVE_ALLOW_ANY)

    cert1 = Zcert()
    assert(cert1.public_txt())

    c1 = Client(interace=iface, task=task, verbose='1', cert=cert1)
    c1.start_zyre()

    cert2 = Zcert()
    assert(cert2.public_txt())

    c2 = Client(interface=iface, task=task, verbose='1', cert=cert2)
    c2.start_zyre()

    sleep(0.01)

    loop = ioloop.IOLoop.instance()
    loop.add_handler(c1.actor, c1.handle_message, zmq.POLLIN)

    def test_fcn():
        c2.shout('ZYRE', 'TEST')
        sleep(1)

    loop.run_sync(test_fcn)

    loop.remove_handler(c1.actor)

    c1.stop_zyre()
    c2.stop_zyre()

    auth.stop()

    # cleanup
    sleep(2)


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


def test_client_gossip_curve(iface):
    ctx = zmq.Context.instance()
    auth = ThreadAuthenticator(ctx)
    auth.start()

    # Tell authenticator to use the certificate in a directory
    auth.configure_curve(domain='*', location=zmq.auth.CURVE_ALLOW_ANY)

    cert1 = Zcert()
    assert (cert1.public_txt())

    gossip_cert = Zcert()
    assert (gossip_cert.public_txt())

    # test with multi-process framework..
    c1 = Client(task=task, verbose='1', gossip_bind='ipc:///tmp/gossip.ipc', endpoint='ipc:///tmp/c1.ipc', cert=cert1)
    c1.start_zyre()

    cert2 = Zcert()
    assert (cert2.public_txt())

    c2 = Client(task=task, verbose='1', gossip_connect='ipc:///tmp/gossip.ipc', endpoint='ipc:///tmp/c2.ipc',
                cert=cert2, gossip_publickey=cert1.public_txt())
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