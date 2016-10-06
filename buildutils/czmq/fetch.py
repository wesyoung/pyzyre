
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

# https://github.com/zeromq/czmq/releases/download/v3.0.2/czmq-3.0.2.tar.gz
bundled_version = (3, 0, 2)
vs = '%i.%i.%i' % bundled_version
libczmq = "czmq-%s.tar.gz" % vs
libczmq_url = "https://github.com/zeromq/czmq/releases/download/v{vs}/{libczmq}".format(
    major=bundled_version[0],
    minor=bundled_version[1],
    vs=vs,
    libczmq=libczmq,
)
libczmq_checksum = "sha256:8bca39ab69375fa4e981daf87b3feae85384d5b40cef6adbe9d5eb063357699a"

bundled_version = (3, 0, 3)
vs = '%i.%i.%i' % bundled_version
libczmq = "czmq-%s.tar.gz" % vs
libczmq_url = 'https://github.com/wesyoung/czmq/archive/bbd3194624531cdd5ca242170527754b21c876d4.tar.gz'
libczmq_checksum = "sha256:c66f46805e6f57994d0a287b755e3c0bd6d417f6984f9393ea7d4266d820f8b5"

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
    if digest != digest_ref:
        fatal("%s %s mismatch:\nExpected: %s\nActual  : %s" % (
            dest, scheme, digest_ref, digest))
    return dest


def fetch_libczmq(savedir):
    dest = pjoin(savedir, 'czmq')
    if os.path.exists(dest):
        info("already have %s" % dest)
        return
    path = fetch_archive(savedir, libczmq_url, fname=libczmq, checksum=libczmq_checksum)
    tf = tarfile.open(path)
    with_version = pjoin(savedir, tf.firstmember.path)
    tf.extractall(savedir)
    tf.close()
    # remove version suffix:
    shutil.move(with_version, dest)


class FetchCommand(Command):

    description = "Fetch libczmq sources into bundled/czmq"

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
        #fetch_libzmq(bundledir)
        fetch_libczmq(bundledir)
        for tarball in glob(pjoin(bundledir, '*.tar.gz')):
            os.remove(tarball)
