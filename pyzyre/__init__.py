# this is really only to maintain versions, you should use and have access to czmq.* and zyre.*

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

from zyre import *