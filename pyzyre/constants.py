from ._version import get_versions
VERSION = get_versions()['version']
del get_versions
import os
import sys

PYVERSION = 2
if sys.version_info > (3,):
    PYVERSION = 3


ZYRE_GROUP = os.environ.get('ZYRE_GROUP', 'ZYRE')
SERVICE_PORT = os.environ.get('ZYRE_SERVICE_PORT', '49155')

GOSSIP_PORT = os.environ.get('ZYRE_SERVICE_PORT', '49154')
GOSSIP_CONNECT = os.getenv('ZYRE_GOSSIP_CONNECT')
ENDPOINT = os.getenv('ZYRE_ENDPOINT')

LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s[%(lineno)s] - %(message)s'

CURVE_ALLOW_ANY = "*"

PUBLIC_KEY = os.getenv('ZYRE_PUBLIC_KEY')
SECRET_KEY = os.getenv('ZYRE_SECRET_KEY')
GOSSIP_PUBLIC_KEY = os.getenv('ZYRE_GOSSIP_PUBLICKEY')

NODE_NAME = os.getenv('ZYRE_NODE_NAME')
ZAUTH_TRACE = os.getenv('ZAUTH_TRACE', False)

CERT_PATH = os.getenv('ZYRE_CERT_PATH', '~/.certs')

LOGLEVEL = os.getenv('ZYRE_LOGLEVEL', 'ERROR')

ZMQ_LINGER = os.getenv('ZMQ_LINGER', 0)
ZYRE_GATEWAY = os.getenv('ZYRE_GATEWAY')