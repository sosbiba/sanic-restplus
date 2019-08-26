#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# flake8: noqa

import io
import os
import re
import sys

from setuptools import setup, find_packages
from setuptools.command.develop import develop
from setuptools.command.install import install

RE_REQUIREMENT = re.compile(r'^\s*-r\s*(?P<filename>.*)$')

PYPI_RST_FILTERS = (
    # Replace Python crossreferences by simple monospace
    (r':(?:class|func|meth|mod|attr|obj|exc|data|const):`~(?:\w+\.)*(\w+)`', r'``\1``'),
    (r':(?:class|func|meth|mod|attr|obj|exc|data|const):`([^`]+)`', r'``\1``'),
    # replace doc references
    (r':doc:`(.+) <(.*)>`', r'`\1 <http://flask-restplus.readthedocs.org/en/stable\2.html>`_'),
    # replace issues references
    (r':issue:`(.+?)`', r'`#\1 <https://github.com/noirbizarre/flask-restplus/issues/\1>`_'),
    # Drop unrecognized currentmodule
    (r'\.\. currentmodule:: .*', ''),
)



class PostDevelopCommand(develop):
    """Post-installation for development mode."""
    def run(self):
        # PUT YOUR POST-INSTALL SCRIPT HERE or CALL A FUNCTION

        develop.run(self)


def rst(filename):
    '''
    Load rst file and sanitize it for PyPI.
    Remove unsupported github tags:
     - code-block directive
     - all badges
    '''
    content = io.open(filename).read()
    for regex, replacement in PYPI_RST_FILTERS:
        content = re.sub(regex, replacement, content)
    return content



def pip(filename):
    '''Parse pip reqs file and transform it to setuptools requirements.'''
    requirements = []
    for line in io.open(os.path.join('requirements', '{0}.pip'.format(filename))):
        line = line.strip()
        if not line or '://' in line or line.startswith('#'):
            continue
        requirements.append(line)
    return requirements


long_description = '\n'.join((
    rst('README.rst'),
    rst('CHANGELOG.rst'),
    ''
))


exec(compile(open('sanic_restplus/__about__.py', encoding="latin-1").read(), 'sanic_restplus/__about__.py', 'exec'))

install_requires = pip('install')
if sys.version_info < (3, 5):
    raise RuntimeError("Cannot install on Python version < 3.5")
doc_require = pip('doc')
tests_require = pip('test')

setup(
    name='sanic-restplus',
    version=__version__,
    description=__description__,
    long_description=long_description,
    url='https://github.com/ashleysommer/sanic-restplus',
    author='Ashley Sommer',
    author_email='ashleysommer@gmail.com',
    packages=find_packages(exclude=['tests', 'tests.*']),
    entry_points={
        'sanic_plugins':
            ['RestPlus = sanic_restplus.restplus:instance']
    },
    include_package_data=True,
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require={
        'test': tests_require,
        'doc': doc_require,
    },
    cmdclass={
        'develop': PostDevelopCommand,
    },
    license='MIT',
    use_2to3=False,
    zip_safe=False,
    keywords='sanic restplus rest api swagger openapi',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python',
        'Environment :: Web Environment',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Topic :: System :: Software Distribution',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: MIT License',
    ],
)
