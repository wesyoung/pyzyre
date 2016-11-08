import os

ZYRE_CHANNEL = os.environ.get('ZYRE_CHANNEL', 'ZYRE')
SERVICE_PORT = os.environ.get('ZYRE_SERVICE_PORT', '49155')

GOSSIP_PORT = os.environ.get('ZYRE_SERVICE_PORT', '49154')
GOSSIP_ENDPOINT = os.environ.get('ZYRE_GOSSIP_ENDPOINT', 'zyre.local')

LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s[%(lineno)s] - %(message)s'
