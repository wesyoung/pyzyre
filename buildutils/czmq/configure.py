from distutils.ccompiler import get_default_compiler, new_compiler
from distutils.extension import Extension
from distutils.command.build_ext import build_ext
from distutils.command.sdist import sdist
import shutil
from glob import glob
from os.path import basename, join as pjoin
from subprocess import Popen, PIPE
import platform
import re
import stat
from ctypes import *

from .msg import *
from .fetch import fetch_libczmq

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
            './configure'

        ]
        info("attempting ./configure to generate platform.h with: {}".format(configure_cmd))
        p = Popen(' '.join(configure_cmd), cwd=zmqroot, shell=True, stdout=PIPE, stderr=PIPE)

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


class ConfigureSDist(sdist):
    def run(self):
        bundledir = "bundled"

        line()
        info("Using bundled libczmq")

        # fetch sources for libzmq extension:
        if not os.path.exists(bundledir):
            os.makedirs(bundledir)

        fetch_libczmq(bundledir)

        bundledincludedir = 'czmq'

        if not os.path.exists(bundledincludedir):
            os.makedirs(bundledincludedir)

        files = [
            pjoin(bundledir, 'czmq', 'bindings', 'python', 'czmq', '_czmq_ctypes.py'),
            pjoin(bundledir, 'czmq', 'bindings', 'python', 'czmq', '__init__.py')
        ]

        for f in files:
            shutil.copyfile(f, pjoin(bundledincludedir, basename(f)))


class Configure(build_ext):

    user_options = build_ext.user_options + [
        ('czmq=', None, "libczmq install prefix"),
        ('build-base=', 'b', "base directory for build library"),  # build_base from build
    ]

    def initialize_options(self):
        build_ext.initialize_options(self)
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

    def bundle_libczmq_extension(self):
        bundledir = "bundled"
        ext_modules = self.distribution.ext_modules

        if ext_modules and any(m.name == 'czmq.libczmq' for m in ext_modules):
            # I've already been run
            return

        line()
        info("Using bundled libczmq")

        # fetch sources for libzmq extension:
        if not os.path.exists(bundledir):
            os.makedirs(bundledir)

        fetch_libczmq(bundledir)

        stage_platform_header(pjoin(bundledir, 'czmq'))

        czmq_sources = []
        for f in glob(pjoin(bundledir, 'czmq', 'src', '*.c')):
            if f not in ['bundled/czmq/src/czmq_selftest.c', 'bundled/czmq/src/zsp.c'] and 'test_' not in f:
                czmq_sources.append(f)

        czmq_sources.append(pjoin('buildutils', 'czmq', 'initlibczmq.c'))

        compile_args = [
            '-std=c99',
            '-Wno-strict-prototypes',
            '-Wno-unused-variable',
            '-Wno-unused-function',
        ]

        if sys.platform != 'darwin':
            compile_args.append('-Wno-unused-but-set-variable')

        library_dirs = [
            pjoin(self.build_lib, 'czmq'),
        ]

        if os.name != 'nt':
            library_dirs.append('/usr/local/lib')  # osx needs this to find ossp-uuid

        libraries = ['zmq', 'uuid']

        if re.search(r'centos-7|Ubuntu-16', platform.platform()):
            libraries.append('systemd')

        libczmq = Extension(
            'czmq.libczmq',
            sources=czmq_sources,
            include_dirs=[
                pjoin(bundledir, 'czmq', 'include'),
                pjoin(bundledir, 'zeromq', 'include')
            ],
            libraries=libraries,
            library_dirs=library_dirs,

            extra_compile_args=compile_args,
            # http://stackoverflow.com/a/19147134
            runtime_library_dirs=['zmq', 'czmq', '.'],
        )

        # http://stackoverflow.com/a/32765319/7205341
        if sys.platform == 'darwin':
            from distutils import sysconfig
            vars = sysconfig.get_config_vars()
            vars['LDSHARED'] = vars['LDSHARED'].replace('-bundle', '-dynamiclib')

        # register the extension:
        self.distribution.ext_modules.insert(1, libczmq)

        libczmq.include_dirs.append(bundledir)

        libczmq.define_macros.append(('WITH_MAKECERT', 0))
        libczmq.define_macros.append(('WITH_TEST_ZGOSSIP', 0))
        libczmq.define_macros.append(('CZMQ_BUILD_DRAFT_API', 1))

        cc = new_compiler(compiler=self.compiler_type)
        cc.output_dir = self.build_temp

        bundledincludedir = 'czmq'

        if not os.path.exists(bundledincludedir):
            os.makedirs(bundledincludedir)

        if not os.path.exists(pjoin(self.build_lib, bundledincludedir)):
            os.makedirs(pjoin(self.build_lib, bundledincludedir))

        files = [
            pjoin(bundledir, 'czmq', 'bindings', 'python', 'czmq', '_czmq_ctypes.py'),
            pjoin(bundledir, 'czmq', 'bindings', 'python', 'czmq', '__init__.py')
        ]

        for f in files:
            shutil.copyfile(f, pjoin(bundledincludedir, basename(f)))
            shutil.copyfile(f, pjoin(self.build_lib, bundledincludedir, basename(f)))

    def run(self):

        self.bundle_libczmq_extension()