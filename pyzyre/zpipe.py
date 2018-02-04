import logging
from argparse import ArgumentParser, RawDescriptionHelpFormatter
import textwrap
import select
import sys

import zmq
from pyzyre.constants import PYVERSION, ZMQ_LINGER, ZYRE_GATEWAY
from pyzyre.utils import setup_logging, get_argument_parser


def main():
    p = get_argument_parser(advanced=False)
    p = ArgumentParser(
        description=textwrap.dedent('''\
                    example usage:
                        $ cat test.eml | zyre-pipe --gateway tcp://192.168.1.2:49100 [-v|-d]
                    '''),
        formatter_class=RawDescriptionHelpFormatter,
        prog='zyre-pipe',
        parents=[p]
    )

    p.add_argument('--gateway', help="sepcify the gateway address [default %(default)s]", default=ZYRE_GATEWAY)
    p.add_argument('--linger', help="specify zmq_linger [default %(default)s]", default=ZMQ_LINGER)

    args = p.parse_args()

    logger = logging.getLogger('')
    setup_logging(args)

    if not select.select([sys.stdin, ], [], [], 0.0)[0]:
        logger.info('Nothing in STDIN to send..')
        raise SystemExit

    ctx = zmq.Context()
    s = ctx.socket(zmq.PUSH)
    s.setsockopt(zmq.LINGER, args.linger)
    s.connect(args.address)

    content = sys.stdin.read().strip('\n')

    if PYVERSION == 2:
        content = unicode(content, encoding='utf-8', errors='ignore')

    logger.info('sending..')
    s.send_multipart([content.encode('utf-8')])
    logger.info('sent...')
    s.close()

    logger.info('done')


if __name__ == '__main__':
    main()
