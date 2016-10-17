import pytest
from pyzyre.utils import resolve_endpoint, resolve_interface, resolve_address
import sys


@pytest.fixture
def interface():
    if sys.platform == 'darwin':
        return 'en0'
    else:
        return 'eth0'


def test_resolve_address(interface):
    addr = resolve_address(interface)
    assert addr


def test_resolve_interface(interface):
    addr = resolve_address(interface)
    assert addr

    i = resolve_interface(addr)
    assert i


def test_resolve_endpoint():
    e = resolve_endpoint(5432)
    assert e
