import pytest
from pyzyre.utils import resolve_endpoint, address_to_interface, resolve_address
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

    i = address_to_interface(addr)
    assert i


def test_resolve_endpoint():
    e = resolve_endpoint('*', port=5432)
    assert e
