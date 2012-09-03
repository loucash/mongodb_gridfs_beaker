mongodb_gridfs_beaker
=====================

MongoDB_. GridFS_. backend for Beaker_.'s caching / session system.

Based upon mongodbbeaker_.

Really basic, first implementation of MongoDB GridFS as a backend storage for Beaker.

.. _Beaker: http://beaker.groovie.org
.. _MongoDB: http://mongodb.org
.. _GridFS: http://www.mongodb.org/display/DOCS/GridFS
.. _mongodbbeaker: http://pypi.python.org/pypi/mongodb_beaker

Configuration
=============

Example of configuration in Pylons project:

    >>> # new style cache settings
    ... beaker.cache.regions = comic_archives, navigation
    ... beaker.cache.comic_archives.type = libmemcached
    ... beaker.cache.comic_archives.url = 127.0.0.1:11211
    ... beaker.cache.comic_archives.expire = 604800
    ... beaker.cache.navigation.type = mongodb_gridfs
    ... beaker.cache.navigation.url = mongodb://localhost:27017/beaker.navigation
    ... beaker.cache.navigation.expire = 86400

Using Beaker Sessions
=====================

Pylons application configuration for mongodb_beaker has the
following session_configuration::

    >>> beaker.session.type = mongodb_gridfs
    ... beaker.session.url = mongodb://localhost:27017/beaker.sessions
