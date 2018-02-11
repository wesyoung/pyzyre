#!/usr/bin/env python

import os
import zmq.auth
from argparse import ArgumentParser
from pprint import pprint

CERTS_PATH = os.getenv('ZYRE_CERTS_PATH', os.path.expanduser('~/.curve'))


def main():
    if zmq.zmq_version_info() < (4,0):
        raise RuntimeError("Security is not supported in libzmq version < 4.0. libzmq version {0}".format(
            zmq.zmq_version()))

    p = ArgumentParser(add_help=False)
    p.add_argument('-d', '--debug', action="store_true")
    p.add_argument('-v', '--verbose', action="store_true")
    p.add_argument('--path', help='specify base path [default %(default)s]', default=CERTS_PATH)
    p.add_argument('--name', help='specify key name [default %(default)s]', default='zyre')

    args = p.parse_args()

    certs = zmq.auth.create_certificates(args.path, 'test', metadata={'name': args.name})
    for c in certs:
        os.chmod(c, 0600)

    print("Generated certs in: %s" % CERTS_PATH)


if __name__ == '__main__':
    main()
