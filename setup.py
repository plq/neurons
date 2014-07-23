#!/usr/bin/env python
#encoding: utf8

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

SHORT_DESC = """Short"""
LONG_DESC  = """Long"""

try:
    os.stat('CHANGELOG.rst')
    LONG_DESC += "\n\n" + open('CHANGELOG.rst', 'r').read()
except OSError:
    pass

##################
### testing stuff

install_reqs = (
    'spyne', 'msgpack-python', 'pycrypto', 'SQLAlchemy', 'werkzeug', 'lxml',
    'Twisted')

test_reqs = install_reqs + ('pytest',)

### testing stuff
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
        'Programming Language :: Python :: 2.6',
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
    install_requires=[
      'spyne',
    ],

    entry_points={
        'console_scripts': [ ],
    },

    tests_require=test_reqs,
)
