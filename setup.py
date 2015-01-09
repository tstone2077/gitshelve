#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

import os.path
from setuptools import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(name='gitshelve',
      version='0.0.0',
      author="John Wiegley, Thurston",
      description='Python object for easily writing scripts that store arbitrary data inside a Git repository.',
      long_description=read('README.md'),
      url='https://github.com/tstone2077/gitshelve',
      py_modules=['gitshelve'],
      test_suite="test",
      license="BSD",
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 3',
          'Intended Audience :: Developers',
          'Topic :: Software Development :: Libraries',
          'Operating System :: OS Independent',
          'License :: OSI Approved :: BSD License'
      ]
      )
