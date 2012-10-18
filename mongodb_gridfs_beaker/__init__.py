#
# * Beaker plugin for MongoDB GridFS support
#
# Lukasz Biedrycki <lukasz.biedrycki@gmail.com>
#
"""
==============
mongodb_gridfs_beaker
==============
MongoDBGridFS backend for Beaker_.'s caching / session system.

Based upon mongodb_beaker code.
"""

import logging
log = logging.getLogger(__name__)

from beaker.container import NamespaceManager, Container
from beaker.exceptions import InvalidCacheBackendError, MissingCacheParameter
from beaker.synchronization import file_synchronizer
from beaker.util import SyncDict, verify_directory

from pymongo.uri_parser import parse_uri
from pymongo.connection import Connection
from pymongo import ASCENDING, DESCENDING

from gridfs import GridFS
from gridfs.errors import NoFile

try:
    import cPickle as pickle
except ImportError:
    import pickle

class MongoDBGridFSNamespaceManager(NamespaceManager):
    
    clients = SyncDict()

    def __init__(self, namespace, url=None, data_dir=None, lock_dir=None, **params):
        NamespaceManager.__init__(self, namespace)

        if lock_dir:
            self.lock_dir = lock_dir
        elif data_dir:
            self.lock_dir = data_dir + "/container_mongodb_gridfs_lock"
        if self.lock_dir:
            verify_directory(self.lock_dir)

        if not url:
            raise MissingCacheParameter("MongoDB url is required")

        for k, v in parse_uri(url).iteritems():
            setattr(self, "url_%s"%k, v)

        if not self.url_database or not self.url_nodelist:
            raise MissingCacheParameter("Invalid MongoDB url.")

        data_key = "mongodb_gridfs:%s:%s" % (self.url_database, self.url_collection)
        self.gridfs = MongoDBGridFSNamespaceManager.clients.get(
                        data_key, self._create_mongo_connection)

    def _create_mongo_connection(self):
        host_uri = \
            'mongodb://%s' % (",".join(["%s:%s" % h for h in self.url_nodelist]))
        log.info("[MongoDBGridFS] Host URI: %s" % host_uri)
        conn = Connection(
                    host_uri, 
                    slaveok=self.url_options.get("slaveOk", False),
                    replicaset=self.url_options.get("replicaSet", None))

        db = conn[self.url_database]

        if self.url_username:
            log.info("[MongoDBGridFS] Attempting to authenticate %s/%s " % 
                     (self.url_username, self.url_password))
            if not db.authenticate(self.url_username, self.url_password):
                raise InvalidCacheBackendError('Cannot authenticate to MongoDB.')

        collection = db["%s.files" % self.url_collection]
        collection.ensure_index(
            [("namespace", ASCENDING), ("filename", ASCENDING)], unique=True)
        collection.ensure_index([("namespace", ASCENDING)])

        return (db, GridFS(db, self.url_collection))

    @property
    def collection(self):
        mongo = self.gridfs[0]
        return mongo["%s.files" % self.url_collection]

    def get_creation_lock(self, key):
        return file_synchronizer(
            identifier = "mongodb_gridfs_container/funclock/%s" % self.namespace,
            lock_dir = self.lock_dir)

    def do_remove(self):
        log.debug("[MongoDBGridFS] Remove namespace: %s" % self.namespace)
        self.collection.remove({'namespace':self.namespace})

    def _get_file_for_key(self, key):
        query = {'namespace': self.namespace, 'filename': key}
        log.debug("[MongoDBGridFS] Get Query: %s", query)
        try:
            result = self.gridfs[1].get_last_version(**query)
        except NoFile:
            result = None
        log.debug("[MongoDBGridFS] Get Result: %s", result)
        return result

    def __getitem__(self, key):
        query = {'namespace': self.namespace, 'filename': key}
        log.debug("[MongoDBGridFS %s] Get Key: %s" % (self.gridfs, query))

        result = self._get_file_for_key(key)
        if not result:
            return None

        value = result.read()
        if not value:
            return None

        try:
            value = pickle.loads(value)
        except Exception, e:
            log.exception("[MongoDBGridFS] Failed to unpickle value.")
            return None

        log.debug("[MongoDBGridFS] key: %s; value: %s" % (key, value))
        return value

    def __contains__(self, key):
        result = self._get_file_for_key(key)
        log.debug("[MongoDBGridFS] Has '%s'? %s" % (key, result))
        return result is not None

    def has_key(self, key):
        return key in self

    def set_value(self, key, value):
        query = {'namespace': self.namespace, 'filename': key}
        log.debug("[MongoDBGridFS %s] Set Key: %s" % (self.gridfs, query))

        try:
            value = pickle.dumps(value)
        except:
            log.exception("[MongoDBGridFS] Failed to pickle value.")
            return None

        mongo, gridfs = self.gridfs
        self.__delitem__(key)
        gridfs.put(value, **query)

    def __setitem__(self, key, value):
        self.set_value(key, value)

    def __delitem__(self, key):
        query = {'namespace': self.namespace, 'key': key}
        log.debug("[MongoDBGridFS %s] Del Key: %s" % (self.gridfs, query))

        for file_id in self.files_ids(key):
            self.gridfs[1].delete(file_id)

    def keys(self):
        docs = self.collection.find({'namespace': self.namespace})
        return [f.get("filename", "") for f in docs]

    def files_ids(self, key):
        docs = self.collection.find({'namespace': self.namespace, 'filename':key})
        return [f.get("_id", "") for f in docs]

class MongoDBGridFSContainer(Container):
    namespace_class = MongoDBGridFSNamespaceManager
