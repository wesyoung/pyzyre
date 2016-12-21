import pytest
from pyzyre.utils import resolve_endpoint, resolve_interface, resolve_address, resolve_gossip
import sys
import netifaces as ni


@pytest.fixture
def iface():
    if sys.platform == 'darwin':
        return 'en0'
    else:
        if 'eth0' in ni.interfaces():
            return 'eth0'
        else:
            return ni.interfaces()[1]


def test_resolve_address(iface):
    addr = resolve_address(iface)
    assert addr


def test_resolve_interface(iface):
    addr = resolve_address(iface)
    assert addr

    i = resolve_interface(addr)
    assert i


def test_resolve_endpoint():
    e = resolve_endpoint(5432)
    assert e


def test_resolve_gossip(iface):
    e = resolve_gossip(5432, address=iface)
    assert e
