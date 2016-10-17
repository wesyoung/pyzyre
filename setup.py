#!/usr/bin/env python

from __future__ import with_statement, print_function

import os
import sys
from distutils.version import LooseVersion
from setuptools import setup, Command
import setuptools.command.build_py
from buildutils.zmq.configure import Configure as ConfigureZmq
from buildutils.czmq.configure import Configure as ConfigureCzmq
from buildutils.zyre.configure import Configure as ConfigureZyre
from ctypes import *

from pprint import pprint

import versioneer

# vagrant doesn't appreciate hard-linking
if os.environ.get('USER') == 'vagrant' or os.path.isdir('/vagrant'):
    del os.link

try:
    import Cython
    if LooseVersion(Cython.__version__) < LooseVersion('0.16'):
        raise ImportError("Cython >= 0.16 required, found %s" % Cython.__version__)
    try:
        # Cython 0.25 or later
        from Cython.Distutils.old_build_ext import old_build_ext as build_ext_c
    except ImportError:
        from Cython.Distutils import build_ext as build_ext_c
except Exception as e:
    raise ImportError('Cython >= 0.16 required')

try:
    cdll.LoadLibrary('libuuid.so')
except OSError:
    raise ImportError('Requires uuid-dev and libuuid1 to be installed')

pypy = 'PyPy' in sys.version


# set dylib ext:
if sys.platform.startswith('win'):
    lib_ext = '.dll'
elif sys.platform == 'darwin':
    lib_ext = '.dylib'
else:
    lib_ext = '.so'

for idx, arg in enumerate(list(sys.argv)):
    if arg == 'egg_info':
        sys.argv.pop(idx)
        sys.argv.insert(idx, 'build')
        sys.argv.insert(idx+1, 'egg_info')


class zbuild_ext(build_ext_c):

    def finalize_options(self):
        build_ext_c.finalize_options(self)
        # set binding so that compiled methods can be inspected
        self.cython_directives['binding'] = True

    def build_extensions(self):
        # if self.compiler.compiler_type == 'mingw32':
        #     customize_mingw(self.compiler)
        return build_ext_c.build_extensions(self)

    def build_extension(self, ext):
        build_ext_c.build_extension(self, ext)

    def run(self):

        self.distribution.run_command('configure_zmq')
        self.distribution.run_command('configure_czmq')
        self.distribution.run_command('configure')

        return build_ext_c.run(self)


class BuildPyCommand(setuptools.command.build_py.build_py):
  """Custom build command."""

  def run(self):
    self.run_command('build_ext')
    setuptools.command.build_py.build_py.run(self)

cmdclass = versioneer.get_cmdclass()
cmdclass = {
    'configure': ConfigureZyre,
    'configure_zmq': ConfigureZmq,
    'configure_czmq': ConfigureCzmq,
    'build_ext': zbuild_ext,
    'build_py': BuildPyCommand,
}

packages = ['pyzyre', 'czmq', 'zyre']

package_data = {
    'zyre': ['*' + lib_ext]
}

extensions = []


setup(
    name="pyzyre",
    version=versioneer.get_version(),
    packages=packages,
    ext_modules=extensions,
    package_data=package_data,
    author="Wes Young",
    author_email="wes@barely3am.com",
    url='https://github.com/wesyoung/pyzyre',
    description="",
    long_description="",
    license="LGPLV3",
    cmdclass=cmdclass,
    install_requires=[
        'netifaces',
        'netaddr',
        'cython>=0.16',
        'pytest'
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
    ],
)

