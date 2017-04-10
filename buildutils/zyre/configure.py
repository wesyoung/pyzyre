from distutils.ccompiler import get_default_compiler, new_compiler
from distutils.extension import Extension
from distutils.command.build_ext import build_ext
from distutils.command.sdist import sdist
import shutil
from glob import glob
from os.path import basename, join as pjoin
from subprocess import Popen, PIPE
from ctypes import *

from .msg import *
from .fetch import fetch_libzyre

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)


def stage_platform_header(zmqroot):
    platform_h = pjoin(zmqroot, 'src', 'platform.h')

    if os.path.exists(platform_h):
        info("already have platform.h")
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

        configure_cmd = [
            'libzmq_CFLAGS=-I../zeromq/include',
            'libzmq_LIBS=-L../zeromq/src',
            'czmq_CFLAGS=-I../czmq/include',
            'czmq_LIBS=-L../czmq/src',
            './configure'

        ]
        info("attempting ./configure to generate platform.h with: {}".format(configure_cmd))
        p = Popen(' '.join(configure_cmd), cwd=zmqroot, shell=True, stdout=PIPE, stderr=PIPE)

        o, e = p.communicate()
        if p.returncode:
            warn("failed to configure libzyre:\n%s" % e)

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


class ConfigureSDist(sdist):
    def run(self):
        bundledir = "bundled"

        line()

        if not os.path.exists(bundledir):
            os.makedirs(bundledir)

        fetch_libzyre(bundledir)

        bundledincludedir = 'zyre'

        if not os.path.exists(bundledincludedir):
            os.makedirs(bundledincludedir)

        files = [
            pjoin(bundledir, 'zyre', 'bindings', 'python', 'zyre', '_zyre_ctypes.py'),
            pjoin(bundledir, 'zyre', 'bindings', 'python', 'zyre', '__init__.py')
        ]

        for f in files:
            shutil.copyfile(f, pjoin(bundledincludedir, basename(f)))
            #shutil.copyfile(f, pjoin(self.build_lib, bundledincludedir, basename(f)))

class Configure(build_ext):

    user_options = build_ext.user_options + [
        ('zyre=', None, "libzyre install prefix"),
        ('build-base=', 'b', "base directory for build library"),  # build_base from build
    ]

    def initialize_options(self):
        build_ext.initialize_options(self)
        self.zmq = None
        self.build_base = 'build'

    # DON'T REMOVE: distutils demands these be here even if they do nothing.
    def finalize_options(self):
        build_ext.finalize_options(self)
        self.tempdir = pjoin(self.build_temp, 'scratch')
        self.has_run = False

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

    def bundle_libzyre_extension(self):
        bundledir = "bundled"
        ext_modules = self.distribution.ext_modules

        if ext_modules and any(m.name == 'zyre.libzyre' for m in ext_modules):
            # I've already been run
            return

        line()
        info("Using bundled libzyre")

        # fetch sources for libzmq extension:
        if not os.path.exists(bundledir):
            os.makedirs(bundledir)

        fetch_libzyre(bundledir)

        stage_platform_header(pjoin(bundledir, 'zyre'))

        zyre_sources = []
        for f in glob(pjoin(bundledir, 'zyre', 'src', '*.c')):
            if f not in ['bundled/zyre/src/ztester_gossip.c', 'bundled/zyre/src/zpinger.c',
                         'bundled/zyre/src/ztester_beacon.c', 'bundled/zyre/src/zyre_selftest.c',
                         'bundled/zyre/src/perf_remote.c']:
                zyre_sources.append(f)

        zyre_sources.append(pjoin('buildutils', 'zyre', 'initlibzyre.c'))

        compile_args = [
            '-std=c99',
            '-Wno-strict-prototypes',
            '-Wno-unused-variable',
            '-Wno-unused-function',
        ]

        if sys.platform != 'darwin':
            compile_args.append('-Wno-unused-but-set-variable')

        libzyre = Extension(
            'zyre.libzyre',
            sources=zyre_sources,
            include_dirs=[
                pjoin(bundledir, 'zeromq', 'include'),
                pjoin(bundledir, 'czmq', 'include'),
                pjoin(bundledir, 'zyre', 'include')
            ],
            libraries=['zmq', 'czmq'],
            library_dirs=[
                pjoin(self.build_lib, 'czmq'),
                pjoin(self.build_lib, 'zyre')
            ],
            extra_compile_args=compile_args,
            # http://stackoverflow.com/a/19147134
            runtime_library_dirs=['zmq', 'czmq', 'zyre', '.'],
        )

        # register the extension:
        self.distribution.ext_modules.insert(2, libzyre)

        libzyre.include_dirs.append(bundledir)

        libzyre.define_macros.append(('ENABLE_DRAFTS', 1))

        cc = new_compiler(compiler=self.compiler_type)
        cc.output_dir = self.build_temp

        bundledincludedir = 'zyre'

        if not os.path.exists(bundledincludedir):
            os.makedirs(bundledincludedir)

        if not os.path.exists(pjoin(self.build_lib, bundledincludedir)):
            os.makedirs(pjoin(self.build_lib, bundledincludedir))

        files = [
            pjoin(bundledir, 'zyre', 'bindings', 'python', 'zyre', '_zyre_ctypes.py'),
            pjoin(bundledir, 'zyre', 'bindings', 'python', 'zyre', '__init__.py')
        ]

        for f in files:
            shutil.copyfile(f, pjoin(bundledincludedir, basename(f)))
            shutil.copyfile(f, pjoin(self.build_lib, bundledincludedir, basename(f)))

    def run(self):

        self.bundle_libzyre_extension()