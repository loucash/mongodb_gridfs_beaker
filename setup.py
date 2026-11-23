#!/usr/bin/env python
#
# Copyright (c) 2012 Lukasz Biedrycki <lukasz.biedrycki@gmail.com>
#
from setuptools import setup, find_packages  # ty: ignore[import-not-found]

setup(
    name = 'mongodb_gridfs_beaker',
    version = '0.6.0dev1',
    description = 'Beaker backend to write sessions and caches to a MongoDB GridFS',
    long_description = '\n' + open('README.md').read(),
    long_description_content_type="text/markdown",
    author='Lukasz Biedrycki',
    author_email = 'lukasz.biedrycki@gmail.com',
    keywords = 'mongo mongodb gridfs beaker cache session',
    license = 'New BSD License',
    url = 'https://github.com/loucash/mongodb_gridfs_beaker',
    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Other Environment',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Database',
        'Topic :: Utilities',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    packages = find_packages(),
    include_package_data=True,
    zip_safe = True,
    entry_points="""
    [beaker.backends]
    mongodb_gridfs = mongodb_gridfs_beaker:MongoDBGridFSNamespaceManager
    """,
    requires=['pymongo', 'beaker'],
    install_requires = [
        'pymongo>=1.9,<5',
        'beaker>=1.5',
        'verlib2',
    ],
    data_files=[("", ['README.md'])],
    package_data={'': ['README.md']},
)
