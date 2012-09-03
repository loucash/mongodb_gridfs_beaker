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
from beaker.util import SyncDict

from pymongo.uri_parser import parse_uri
from pymongo.connection import Connection
from gridfs import GridFS
from gridfs.errors import NoFile

try:
    import cPickle as pickle
except ImportError:
    import pickle

class MongoDBGridFSNamespaceManager(NamespaceManager):
    
    clients = SyncDict()

    def __init__(self, namespace, url=None, **params):
        NamespaceManager.__init__(self, namespace)

        if not url:
            raise MissingCacheParameter("MongoDB url is required")

        parsed_url = parse_uri(url)
        self.collection = parsed_url['collection']
        log.debug(parsed_url)

        if not (parsed_url['database'] and parsed_url['nodelist']):
            raise MissingCacheParameter("Invalid MongoDB url.")

        data_key = "mongodb_gridfs:%s:%s" % (parsed_url['database'], parsed_url['collection'])

        def _create_mongo_conn():
            host_uri = \
                'mongodb://%s' % (",".join(["%s:%s" % h for h in parsed_url['nodelist']]))
            log.info("Host URI: %s" % host_uri)
            conn = Connection(host_uri)

            db = conn[parsed_url['database']]

            if parsed_url['username']:
                log.info("Attempting to authenticate %s/%s " % 
                         (parsed_url['username'], parsed_url['password']))
                if not db.authenticate(parsed_url['username'], parsed_url['password']):
                    raise InvalidCacheBackendError('Cannot authenticate to MongoDB.')
            return (db, GridFS(db, parsed_url['collection']))

        self.gridfs = MongoDBGridFSNamespaceManager.clients.get(data_key, _create_mongo_conn)

    def get_creation_lock(self, key):
        return file_synchronizer(
            identifier = "mongodb_gridfs_container/funclock/%s" % self.namespace,
            lock_dir = None)

    def do_remove(self):
        log.debug("[MongoDB] Remove namespace: %s" % self.namespace)
        mongo = self.gridfs[0]
        collection = mongo["%s.files" % self.collection]
        collection.remove({'namespace':self.namespace})

    def __getitem__(self, key):
        log.debug("[MongoDB %s] Get Key: %s" % (self.gridfs, key))

        query = {'namespace': self.namespace, 'filename': key}

        log.debug("[MongoDB] Get Query: %s", query)
        try:
            result = self.gridfs[1].get_last_version(**query)
        except NoFile:
            result = None
        log.debug("[MongoDB] Get Result: %s", result)

        if not result:
            return None

        value = result.read()

        if not value:
            return None

        try:
            value = pickle.loads(value.encode('utf-8'))
        except Exception, e:
            log.exception("Failed to unpickle value.", e)
            return None

        log.debug("[key: %s] Value: %s" % (key, value))

        return value

    def __contains__(self, key):
        log.debug("[MongoDB] Has '%s'? " % key)
        result = self.__getitem__(key)
        if not result:
            return None
        log.debug("[MongoDB] %s == %s" % (key, result))
        return result is not None

    def has_key(self, key):
        return key in self

    def set_value(self, key, value, expiretime=None):
        log.debug("[MongoDB %s] Set Key: %s (Expiry: %s) ... " %
                 (self.gridfs, key, expiretime))

        _id = {}
        doc = {}

        try:
            value = pickle.dumps(value)
        except:
            log.exception("Failed to pickle value.")

        query = {'namespace': self.namespace, 'filename': key}
        mongo, gridfs = self.gridfs
        self.__delitem__(key)
        gridfs.put(value, **query)

    def __setitem__(self, key, value):
        self.set_value(key, value)

    def __delitem__(self, key):
        mongo, gridfs = self.gridfs
        query = {'namespace': self.namespace, 'key': key}
        log.debug("[MongoDB %s] Del Key: %s" %
                 (self.gridfs, key))
        log.debug(self.keys())

        for file_id in self._files_ids():
            gridfs.delete(file_id)

    def keys(self):
        mongo = self.gridfs[0]
        collection = mongo["%s.files" % self.collection]
        return [f.get("filename", "") for f in collection.find({'namespace': self.namespace})]

    def _files_ids(self):
        mongo = self.gridfs[0]
        collection = mongo["%s.files" % self.collection]
        return [f.get("_id", "") for f in collection.find({'namespace': self.namespace})]

class MongoDBGridFSContainer(Container):
    namespace_class = MongoDBGridFSNamespaceManager
