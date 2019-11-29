#!/usr/bin/env python

from setuptools import setup

setup(name='github_helper',
      version='1.0',
      description='A batch processing tool for GitHub',
      author='James Percival',
      author_email='j.percival@imperial.ac.uk',
      packages=['github_helper'],
      include_package_data=True,
      scripts=['bin/github_helper']
     )
