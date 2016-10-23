#!/usr/bin/env python

# Python
import sys

# Setuptools
from setuptools import setup

# APB
from apb import __version__

install_requires = []
if sys.version_info < (2, 7):
    install_requires.append('argparse')

setup(
    name='apb',
    version=__version__,
    author='Nine More Minutes, Inc.',
    author_email='chris@ninemoreminutes.com',
    description='Ansible Playbook Wrapper',
    long_description='Lightweight wrapper around ansible-playbook',
    license='BSD',
    keywords='ansible playbook devops',
    url='http://github.com/ninemoreminutes/apb',
    packages=['apb'],
    include_package_data=True,
    zip_safe=False,
    setup_requires=[],
    install_requires=install_requires,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators'
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2 :: Only',
        'Topic :: System :: Installation/Setup',
        'Topic :: System :: Systems Administration',
    ],
    entry_points = {
        'console_scripts': [
            'apb = apb.runner:main',
        ],
    },
    data_files=[],
    options = {
        'egg_info': {
            'tag_build': '-dev',
        },
        'aliases': {
            'dev_build': 'clean --all egg_info sdist',
            'release_build': 'clean --all egg_info -b "" sdist',
        },
    },
)
