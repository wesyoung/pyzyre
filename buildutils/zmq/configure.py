from __future__ import with_statement, print_function

import os
import shutil
import sys

from distutils.ccompiler import get_default_compiler
from distutils.ccompiler import new_compiler
from distutils.extension import Extension
from distutils.command.build_ext import build_ext

from glob import glob
from os.path import basename, join as pjoin
from os.path import basename, join as pjoin
from subprocess import Popen, PIPE

from .bundle import bundled_version, fetch_libzmq, localpath
from .msg import fatal, warn, info, line


libzmq_name = 'libzmq'
pypy = 'PyPy' in sys.version

# reference points for zmq compatibility

min_legacy_zmq = (2, 1, 4)
min_good_zmq = (3, 2)
target_zmq = bundled_version
dev_zmq = (target_zmq[0], target_zmq[1] + 1, 0)

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)

# set dylib ext:
if sys.platform.startswith('win'):
    lib_ext = '.dll'
elif sys.platform == 'darwin':
    lib_ext = '.dylib'
else:
    lib_ext = '.so'


def stage_platform_header(zmqroot):
    platform_h = pjoin(zmqroot, 'src', 'platform.hpp')

    if os.path.exists(platform_h):
        info("already have platform.hpp")
        return

    if os.name == 'nt':
        # stage msvc platform header
        platform_dir = pjoin(zmqroot, 'builds', 'msvc')
    else:
        if not os.path.exists(pjoin(zmqroot, 'configure')):
            info('attempting bash autogen.sh')
            p = Popen('./autogen.sh', cwd=zmqroot, shell=True, stdout=PIPE, stderr=PIPE)
            o, e = p.communicate()
            if p.returncode:
                raise RuntimeError('Failed to run autoconf...')

        info("attempting ./configure to generate platform.h")

        p = Popen('./configure', cwd=zmqroot, shell=True, stdout=PIPE, stderr=PIPE)

        o, e = p.communicate()
        if p.returncode:
            warn("failed to configure libczmq:\n%s" % e)

            if sys.platform == 'darwin':
                platform_dir = pjoin(HERE, 'include_darwin')
            elif sys.platform.startswith('freebsd'):
                platform_dir = pjoin(HERE, 'include_freebsd')
            elif sys.platform.startswith('linux-armv'):
                platform_dir = pjoin(HERE, 'include_linux-armv')
            else:
                platform_dir = pjoin(HERE, 'include_linux')
        else:
            return

    info("staging platform.h from: %s" % platform_dir)
    shutil.copy(pjoin(platform_dir, 'platform.h'), platform_h)


class Configure(build_ext):
    """Configure command adapted from h5py"""

    description = "Discover ZMQ version and features"

    user_options = build_ext.user_options + [
        ('zmq=', None, "libzmq install prefix"),
        ('build-base=', 'b', "base directory for build library"),  # build_base from build
        ('embed', None, '')

    ]

    def initialize_options(self):
        build_ext.initialize_options(self)
        self.zmq = None
        self.build_base = 'build'
        self.embed = False

    # DON'T REMOVE: distutils demands these be here even if they do nothing.
    def finalize_options(self):
        build_ext.finalize_options(self)
        self.tempdir = pjoin(self.build_temp, 'scratch')
        self.has_run = False

    def create_tempdir(self):
        self.erase_tempdir()
        os.makedirs(self.tempdir)
        if sys.platform.startswith('win'):
            # fetch libzmq.dll into local dir
            local_dll = pjoin(self.tempdir, libzmq_name + '.dll')
            if not self.config['zmq_prefix'] and not os.path.exists(local_dll):
                fatal("ZMQ directory must be specified on Windows via setup.cfg"
                      " or 'python setup.py configure --zmq=/path/to/zeromq2'")

            try:
                shutil.copy(pjoin(self.config['zmq_prefix'], 'lib', libzmq_name + '.dll'), local_dll)
            except Exception:
                if not os.path.exists(local_dll):
                    warn("Could not copy " + libzmq_name + " into zmq/, which is usually necessary on Windows."
                                                           "Please specify zmq prefix via configure --zmq=/path/to/zmq or copy "
                         + libzmq_name + " into zmq/ manually.")

    def erase_tempdir(self):
        try:
            shutil.rmtree(self.tempdir)
        except Exception:
            pass

    @property
    def compiler_type(self):
        compiler = self.compiler
        if compiler is None:
            return get_default_compiler()
        elif isinstance(compiler, str):
            return compiler
        else:
            return compiler.compiler_type

    @property
    def cross_compiling(self):
        return self.config['bdist_egg'].get('plat-name', sys.platform) != sys.platform

    def bundle_libzmq_extension(self):
        bundledir = "bundled"
        ext_modules = self.distribution.ext_modules
        if ext_modules and any(m.name == 'czmq.libzmq' for m in ext_modules):
            # I've already been run
            return

        line()
        info("Using bundled libzmq")

        # fetch sources for libzmq extension:
        if not os.path.exists(bundledir):
            os.makedirs(bundledir)

        fetch_libzmq(bundledir)

        stage_platform_header(pjoin(bundledir, 'zeromq'))

        sources = [pjoin('buildutils', 'zmq', 'initlibzmq.c')]
        sources += glob(pjoin(bundledir, 'zeromq', 'src', '*.cpp'))

        includes = [
            pjoin(bundledir, 'zeromq', 'include')
        ]

        if bundled_version < (4, 2, 0):
            tweetnacl = pjoin(bundledir, 'zeromq', 'tweetnacl')
            tweetnacl_sources = glob(pjoin(tweetnacl, 'src', '*.c'))

            randombytes = pjoin(tweetnacl, 'contrib', 'randombytes')
            if sys.platform.startswith('win'):
                tweetnacl_sources.append(pjoin(randombytes, 'winrandom.c'))
            else:
                tweetnacl_sources.append(pjoin(randombytes, 'devurandom.c'))

            sources += tweetnacl_sources
            includes.append(pjoin(tweetnacl, 'src'))
            includes.append(randombytes)
        else:
            # >= 4.2
            sources += glob(pjoin(bundledir, 'zeromq', 'src', 'tweetnacl.c'))

        libzmq = Extension(
            'czmq.libzmq',
            sources=sources,
            include_dirs=includes,
        )

        # http://stackoverflow.com/a/32765319/7205341
        if sys.platform == 'darwin':
            from distutils import sysconfig
            vars = sysconfig.get_config_vars()
            vars['LDSHARED'] = vars['LDSHARED'].replace('-bundle', '-dynamiclib')

        # register the extension:
        self.distribution.ext_modules.insert(0, libzmq)

        # use tweetnacl to provide CURVE support
        libzmq.define_macros.append(('ZMQ_HAVE_CURVE', 1))
        libzmq.define_macros.append(('ZMQ_USE_TWEETNACL', 1))

        # select polling subsystem based on platform
        if sys.platform == 'darwin' or 'bsd' in sys.platform:
            libzmq.define_macros.append(('ZMQ_USE_KQUEUE', 1))
        elif 'linux' in sys.platform:
            libzmq.define_macros.append(('ZMQ_USE_EPOLL', 1))
        elif sys.platform.startswith('win'):
            libzmq.define_macros.append(('ZMQ_USE_SELECT', 1))
        else:
            # this may not be sufficiently precise
            libzmq.define_macros.append(('ZMQ_USE_POLL', 1))

        if sys.platform.startswith('win'):
            # include defines from zeromq msvc project:
            libzmq.define_macros.append(('FD_SETSIZE', 16384))
            libzmq.define_macros.append(('DLL_EXPORT', 1))
            libzmq.define_macros.append(('_CRT_SECURE_NO_WARNINGS', 1))

            # When compiling the C++ code inside of libzmq itself, we want to
            # avoid "warning C4530: C++ exception handler used, but unwind
            # semantics are not enabled. Specify /EHsc".
            if self.compiler_type == 'msvc':
                libzmq.extra_compile_args.append('/EHsc')
            elif self.compiler_type == 'mingw32':
                libzmq.define_macros.append(('ZMQ_HAVE_MINGW32', 1))

            # And things like sockets come from libraries that must be named.
            libzmq.libraries.extend(['rpcrt4', 'ws2_32', 'advapi32'])

            # bundle MSCVP redist
            if self.config['bundle_msvcp']:
                cc = new_compiler(compiler=self.compiler_type)
                cc.initialize()
                # get vc_redist location via private API
                try:
                    cc._vcruntime_redist
                except AttributeError:
                    # fatal error if env set, warn otherwise
                    msg = fatal if os.environ.get("PYZMQ_BUNDLE_CRT") else warn
                    msg("Failed to get cc._vcruntime via private API, not bundling CRT")
                if cc._vcruntime_redist:
                    redist_dir, dll = os.path.split(cc._vcruntime_redist)
                    to_bundle = [
                        pjoin(redist_dir, dll.replace('vcruntime', name))
                        for name in ('msvcp', 'concrt')
                        ]
                    for src in to_bundle:
                        dest = localpath('zmq', basename(src))
                        info("Copying %s -> %s" % (src, dest))
                        # copyfile to avoid permission issues
                        shutil.copyfile(src, dest)

        else:
            libzmq.include_dirs.append(bundledir)

            # check if we need to link against Realtime Extensions library
            cc = new_compiler(compiler=self.compiler_type)
            cc.output_dir = self.build_temp
            libzmq.libraries.append("stdc++")
            if not sys.platform.startswith(('darwin', 'freebsd')):
                line()
                info("checking for timer_create")
                if not cc.has_function('timer_create'):
                    info("no timer_create, linking librt")
                    libzmq.libraries.append('rt')
                else:
                    info("ok")

                if pypy:
                    # seem to need explicit libstdc++ on linux + pypy
                    # not sure why
                    libzmq.libraries.append("stdc++")

    def run(self):
        self.bundle_libzmq_extension()
