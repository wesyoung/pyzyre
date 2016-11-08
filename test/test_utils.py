import pytest
from pyzyre.utils import resolve_endpoint, resolve_interface, resolve_address, resolve_gossip
import sys


@pytest.fixture
def iface():
    if sys.platform == 'darwin':
        return 'en0'
    else:
        return 'eth0'


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
