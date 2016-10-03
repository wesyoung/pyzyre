from __future__ import with_statement, print_function

from setuptools import Command
import os
from os.path import join as pjoin
from glob import glob
import shutil
import sys

class CleanCommand(Command):
    """Custom distutils command to clean the .so and .pyc files."""
    user_options = [('all', 'a',
                     "remove all build output, not just temporary by-products")
                    ]

    boolean_options = ['all']

    def initialize_options(self):
        self.all = None

    def finalize_options(self):
        pass

    def run(self):
        _clean_me = []
        _clean_trees = []

        for d in ('build', 'dist', 'conf'):
            if os.path.exists(d):
                _clean_trees.append(d)

        for root, dirs, files in os.walk('buildutils'):
            if any(root.startswith(pre) for pre in _clean_trees):
                continue
            for f in files:
                if os.path.splitext(f)[-1] == '.pyc':
                    _clean_me.append(pjoin(root, f))

            if '__pycache__' in dirs:
                _clean_trees.append(pjoin(root, '__pycache__'))

        for root, dirs, files in os.walk('zmq'):
            if any(root.startswith(pre) for pre in _clean_trees):
                continue

            for f in files:
                if os.path.splitext(f)[-1] in ('.pyc', '.so', '.o', '.pyd', '.json'):
                    _clean_me.append(pjoin(root, f))

            for d in dirs:
                if d == '__pycache__':
                    _clean_trees.append(pjoin(root, d))

        # remove generated cython files
        if self.all:
            for root, dirs, files in os.walk(pjoin('zmq', 'backend', 'cython')):
                if os.path.splitext(f)[-1] == '.c':
                    _clean_me.append(pjoin(root, f))

        bundled = glob(pjoin('zmq', 'libzmq*'))
        _clean_me.extend([b for b in bundled if b not in _clean_me])

        bundled_headers = glob(pjoin('zmq', 'include', '*.h'))
        _clean_me.extend([h for h in bundled_headers if h not in _clean_me])

        for clean_me in _clean_me:
            print("removing %s" % clean_me)
            try:
                os.unlink(clean_me)
            except Exception as e:
                print(e, file=sys.stderr)
                for clean_tree in _clean_trees:
                    print("removing %s/" % clean_tree)
                    try:
                        shutil.rmtree(clean_tree)
                    except Exception as e:
                        print(e, file=sys.stderr)
