#!/bin/env python
# encoding: utf-8

import os
import re

from setuptools import setup
from setuptools import find_packages


ROOT_NAME = 'garage'

v = open(os.path.join(os.path.dirname(__file__), ROOT_NAME, '__init__.py'))
VERSION = re.compile(r".*__version__ = '(.*?)'", re.S).match(v.read()).group(1)


setup(
    name=ROOT_NAME,
    version=VERSION,
    packages=find_packages(),

    install_requires=['neurons>=0.5'],
    entry_points={
        'console_scripts': [
            'garage_daemon=garage.main:main_daemon',
        ],
    },

    package_data={

    },

    author='Burak Arslan',
    author_email='burak.arslan@arskom.com.tr',

    description="Example Garage Management Project",
)
