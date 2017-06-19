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
