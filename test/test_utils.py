import pytest
from pyzyre.utils import resolve_endpoint, resolve_interface, resolve_address, resolve_gossip
import sys


@pytest.fixture
def interface():
    if sys.platform == 'darwin':
        return 'en0'
    else:
        return 'eth0'


def test_resolve_address(i):
    addr = resolve_address(i)
    assert addr


def test_resolve_interface(i):
    addr = resolve_address(i)
    assert addr

    i = resolve_interface(addr)
    assert i


def test_resolve_endpoint():
    e = resolve_endpoint(5432)
    assert e


def test_resolve_gossip(i):
    e = resolve_gossip(5432, address=i)
