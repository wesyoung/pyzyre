import netifaces as ni
import netaddr
import os.path
import socket
from pprint import pprint


def resolve_interface(address):
    address = netaddr.IPAddress(address)

    for i in ni.interfaces():
        ii = ni.ifaddresses(i)
        if not ii.get(ni.AF_INET):
            continue

        ii = ii[ni.AF_INET]
        ii = netaddr.IPNetwork('{}/{}'.format(ii[0]['addr'], ii[0]['netmask']))
        try:
            if address in ii:
                return i
        except AttributeError:
            pass


def resolve_address(i):
    return interface_to_address(i)


def interface_to_address(i):
    i = ni.ifaddresses(i)
    i = i[ni.AF_INET]
    i = i[0]['addr']
    return i


def default_address():
    i = default_interface()
    return interface_to_address(i)


def default_interface():
    try:
        return ni.gateways()['default'][ni.gateways()['default'].keys()[0]][1]
    except IndexError:
        raise RuntimeError("Unable to determine endpoint address")


def resolve_endpoint(port, address=None, interface=None):
    endpoint = address

    if address:
        if address.startswith(('ipc://', 'tcp://', 'udp://')):
            return address

        try:
            # is it an ip address?
            socket.inet_aton(address)
        except socket.error:
            try:
                # is it an FQDN?
                socket.gethostbyname(address)
            except socket.error:
                if os.path.basename(address):
                    return 'ipc://{}'.format(address)

        if 'tcp://' not in address:
            endpoint = 'tcp://%s' % address

        if port not in address:
            endpoint = '{}:{}'.format(endpoint, port)

        return endpoint

    if interface and interface != '*':
        i = interface_to_address(interface)
        endpoint = 'tcp://{}:{}'.format(i, port)
        return endpoint

    endpoint = default_address()
    endpoint = 'tcp://{}:{}'.format(endpoint, port)

    return endpoint


def resolve_gossip(port, address=None):
    if not address:
        address = resolve_endpoint(port)
    elif len(address) <= 5:
        # they sent us an interface...
        address = resolve_endpoint(port, interface=address)
    else:
        address = resolve_endpoint(port, address)

    return address
