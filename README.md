# mongodb_gridfs_beaker

[MongoDB] [GridFS] backend for [Beaker]'s caching / session system.

Based upon [mongodb_beaker].

Really basic, first implementation of MongoDB GridFS as a backend
storage for Beaker.

# Configuration

Example configuration in Pylons project.

```ini
beaker.cache.regions = comic_archives, navigation

beaker.cache.comic_archives.type = libmemcached
beaker.cache.comic_archives.url = 127.0.0.1:11211
beaker.cache.comic_archives.expire = 604800

beaker.cache.navigation.type = mongodb_gridfs
beaker.cache.navigation.url = mongodb://localhost:27017/beaker.navigation
beaker.cache.navigation.expire = 86400
```

# Using Beaker Sessions

Pylons application configuration for `mongodb_beaker` has the following
session configuration.

```ini
beaker.session.type = mongodb_gridfs
beaker.session.url = mongodb://localhost:27017/beaker.sessions
```


[Beaker]: https://beaker.readthedocs.io/
[GridFS]: https://www.mongodb.com/docs/manual/core/gridfs/
[MongoDB]: https://github.com/mongodb/mongo
[mongodb_beaker]: https://pypi.org/project/mongodb_beaker/
