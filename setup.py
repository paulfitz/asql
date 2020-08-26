#!/usr/bin/env python

import os
from setuptools import setup
import sys

install_requires = [
    "catsql >= 0.4.13",
    "csvkit >= 1.0.5",
    "daff >= 1.3.14",
    "docker >= 4.3.0",
    "openpyxl >= 2.4.1",
    "Pygments >= 2.6.1",
    "pyyaml >= 5.3.1",
    "requests >= 2.24.0",
    "six >= 1.7.3",
    "SQLAlchemy >= 1.0.11",
    "sqlparse >= 0.3.1",
]

def read(fname):
    with open(os.path.join(os.path.dirname(__file__), fname)) as f:
        return f.read()

setup(name="asql",
      version="0.1.3",
      author="Paul Fitzpatrick",
      author_email="paulfitz@alum.mit.edu",
      description="Query a database in natural language",
      packages=['asql'],
      entry_points={
          "console_scripts": [
              "asql=asql.main:main"
          ]
      },
      install_requires=install_requires,
      extras_require={
          "postgres": [
              "psycopg2"
          ],
          "mysql": [
              "mysqlclient"
          ]
      },
      tests_require=[
          'mock',
          'nose'
      ],
      test_suite="nose.collector",
      url="https://github.com/paulfitz/asql",
      long_description=read('README.md'),
      long_description_content_type='text/markdown',
)
