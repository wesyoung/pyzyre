import os
import re
import socket
import netifaces as ni
import netaddr
import dns.resolver
from pprint import pprint


def resolve_address(i):
    return interface_to_address(i)


def interface_to_address(i):
    if ':*' in i:
        i = i.split(':')[0]

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


def resolve_endpoint(endpoint, port):
    if len(endpoint) <= 5:
        # we likely have an interface
        if endpoint == '*':
            endpoint = default_address()
            endpoint = 'tcp://{}:{}'.format(endpoint, port)
            return endpoint

        endpoint = interface_to_address(endpoint)
        endpoint = 'tcp://{}:{}'.format(endpoint, port)
        return endpoint

    if endpoint.startswith('ipc://'):
        return endpoint

    if os.path.exists(endpoint):
        return 'ipc://{}'.format(endpoint)

    if endpoint.startswith(('tcp://', 'udp://')):
        if not re.search(r':\d{1,5}$', endpoint):
            endpoint = '%s:%s' % (endpoint, port)

        return endpoint

    # is it an ip address?
    try:
        socket.inet_aton(endpoint)
    except socket.error:
        return None

    # is it an FQDN?
    try:
        socket.gethostbyname(endpoint)
    except socket.error:
        return None

    if 'tcp://' not in endpoint:
        endpoint = 'tcp://%s' % endpoint

    if not re.search(r':\d{1,5}$', endpoint):
        endpoint = '%s:%s' % (endpoint, port)

    return endpoint


def address_to_interface(address):
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
