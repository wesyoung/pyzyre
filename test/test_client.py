import netifaces as ni
import sys
from time import sleep

import pytest

import zmq
import zmq.auth
from czmq import Zcert
from pyzyre.client import Client
from pyzyre.client._task import task
from zmq.auth.thread import ThreadAuthenticator
from zmq.eventloop import ioloop

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
    c1 = Client(interface=iface)
    c1.start_zyre()

    c2 = Client(interface=iface)
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
    #zauth = Client()._zauth()
    zauth = None

    cert1 = Zcert()
    assert(cert1.public_txt())

    c1 = Client(interace=iface, cert=cert1, zauth=zauth)
    c1.start_zyre()

    sleep(0.01)

    cert2 = Zcert()
    assert(cert2.public_txt())

    c2 = Client(interface=iface, task=task, verbose='1', cert=cert2, zauth=zauth)
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

    # cleanup
    sleep(2)


def test_client_gossip(iface):
    # test with multi-process framework..
    c1 = Client(gossip_bind='ipc:///tmp/gossip.ipc', endpoint='ipc:///tmp/c1.ipc')
    c1.start_zyre()

    c2 = Client(gossip_connect='ipc:///tmp/gossip.ipc', endpoint='ipc:///tmp/c2.ipc')
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
    c1 = Client(gossip_bind='ipc:///tmp/gossip.ipc', endpoint='ipc:///tmp/c1.ipc', cert=cert1)
    c1.start_zyre()

    cert2 = Zcert()
    assert (cert2.public_txt())

    c2 = Client(gossip_connect='ipc:///tmp/gossip.ipc', endpoint='ipc:///tmp/c2.ipc',
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