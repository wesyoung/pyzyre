
import os
import shutil
import tarfile
import hashlib
from setuptools import Command
from glob import glob

try:
    from urllib2 import urlopen
except ImportError:
    from urllib.request import urlopen

from .msg import fatal, debug, info, warn

pjoin = os.path.join

# https://github.com/zeromq/zyre/archive/v2.0.0.tar.gz
# the reg releases do not include the bindings dir(?)
bundled_version = (2, 0, 0)
vs = '%i.%i.%i' % bundled_version
libzyre = "zyre-%s.tar.gz" % vs
libzyre_url = "https://github.com/zeromq/zyre/archive/v{vs}.tar.gz".format(
    vs=vs,
)
libzyre_checksum = "sha256:b978a999947ddb6722d956db2427869b313225e50518c4fbbf960a68109e3e91"

if os.getenv("PYZYRE_BUILD_MASTER", False) == '1':
    libzyre_url = "https://github.com/zeromq/zyre/archive/master.tar.gz"


HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------

def untgz(archive):
    return archive.replace('.tar.gz', '')


def localpath(*args):
    """construct an absolute path from a list relative to the root pyzmq directory"""
    plist = [ROOT] + list(args)
    return os.path.abspath(pjoin(*plist))


def checksum_file(scheme, path):
    """Return the checksum (hex digest) of a file"""
    h = getattr(hashlib, scheme)()

    with open(path, 'rb') as f:
        chunk = f.read(65535)
        while chunk:
            h.update(chunk)
            chunk = f.read(65535)
    return h.hexdigest()


def fetch_archive(savedir, url, fname, checksum, force=False):
    """download an archive to a specific location"""
    dest = pjoin(savedir, fname)
    scheme, digest_ref = checksum.split(':')

    if os.path.exists(dest) and not force:
        info("already have %s" % dest)
        digest = checksum_file(scheme, fname)
        # skip digest check if we're using master... used in testing new builds
        if libzyre_url == 'https://github.com/zeromq/zyre/archive/master.tar.gz':
            return dest
        if digest == digest_ref:
            return dest
        else:
            warn("but checksum %s != %s, redownloading." % (digest, digest_ref))
            os.remove(fname)

    info("fetching %s into %s" % (url, savedir))
    if not os.path.exists(savedir):
        os.makedirs(savedir)
    req = urlopen(url)
    with open(dest, 'wb') as f:
        f.write(req.read())
    digest = checksum_file(scheme, dest)
    if digest != digest_ref and libzyre_url != 'https://github.com/zeromq/zyre/archive/master.tar.gz':
        fatal("%s %s mismatch:\nExpected: %s\nActual  : %s" % (
            dest, scheme, digest_ref, digest))
    return dest


def fetch_libzyre(savedir):
    dest = pjoin(savedir, 'zyre')
    if os.path.exists(dest):
        info("already have %s" % dest)
        return
    path = fetch_archive(savedir, libzyre_url, fname=libzyre, checksum=libzyre_checksum)
    tf = tarfile.open(path)
    with_version = pjoin(savedir, tf.firstmember.path)
    tf.extractall(savedir)
    tf.close()
    # remove version suffix:
    shutil.move(with_version, dest)


class FetchCommand(Command):

    description = "Fetch libzyre sources into bundled/zyre"

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        # fetch sources for libzmq extension:
        bundledir = "bundled"
        if os.path.exists(bundledir):
            info("Scrubbing directory: %s" % bundledir)
            shutil.rmtree(bundledir)
        if not os.path.exists(bundledir):
            os.makedirs(bundledir)
        fetch_libzyre(bundledir)
        for tarball in glob(pjoin(bundledir, '*.tar.gz')):
            os.remove(tarball)
