#!/usr/bin/env python
# encoding: utf8

from __future__ import print_function

import os
import re
import sys

from setuptools import setup
from setuptools import find_packages
from setuptools.command.test import test as TestCommand


try:
    import colorama

    colorama.init()
    from colorama import Fore

    RESET = Fore.RESET
    GREEN = Fore.GREEN
    RED = Fore.RED
except ImportError:
    RESET = ''
    GREEN = ''
    RED = ''

import inspect
from os.path import join, dirname, abspath

OWN_PATH = abspath(inspect.getfile(inspect.currentframe()))
EXAMPLES_DIR = join(dirname(OWN_PATH), 'examples')

v = open(os.path.join(os.path.dirname(__file__), 'neurons', '__init__.py'), 'r')
VERSION = re.match(r".*__version__ = '(.*?)'", v.read(), re.S).group(1)

SHORT_DESC = """Neurons is a web framework tying together Spyne, Twisted and SQLAlchemy."""
LONG_DESC = SHORT_DESC

try:
    os.stat('CHANGELOG.rst')
    LONG_DESC += "\n\n" + open('CHANGELOG.rst', 'r').read()
except OSError:
    pass


common_reqs = ('spyne>=2.12', 'SQLAlchemy', 'Twisted>=15.2',
    'lxml>=3.4.1', 'pyyaml', 'msgpack-python', 'pycrypto',
)


test_reqs = common_reqs + ('pytest', 'pytest-cov', 'pytest-twisted',
    'tox',
)

install_reqs = common_reqs + (
    'werkzeug',  'psycopg2>=2.5', 'txpostgres',
)

##################
# testing stuff

class Tox(TestCommand):
    user_options = [('tox-args=', 'a', "Arguments to pass to tox")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.tox_args = None

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        #import here, cause outside the eggs aren't loaded
        import tox
        import shlex

        errno = tox.cmdline(args=shlex.split(self.tox_args))
        sys.exit(errno)

# testing stuff
##################

setup(
    name='neurons',
    packages=find_packages(),

    version=VERSION,
    description=SHORT_DESC,
    long_description=LONG_DESC,
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Operating System :: OS Independent',
        'Natural Language :: English',
        'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    keywords=('http',),
    author='Burak Arslan',
    author_email='burak+neurons@arskom.com.tr',
    maintainer='Burak Arslan',
    maintainer_email='burak+neurons@arskom.com.tr',
    url='http://spyne.io/neurons',
    license='LGPL-2.1',
    zip_safe=False,
    install_requires=install_reqs,

    entry_points={
        'console_scripts': [],
    },

    package_data={
        'neurons.form.const': ['*.html'],
        'neurons.daemon.dowser.const': ['*.html', '*.css'],
    },

    tests_require=test_reqs,
    cmdclass={'test': Tox},
)
