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
from typing import Any, Dict, List

log = logging.getLogger(__name__)

from beaker.container import NamespaceManager, Container
from beaker.exceptions import InvalidCacheBackendError, MissingCacheParameter
from beaker.synchronization import file_synchronizer
from beaker.util import SyncDict, verify_directory

# Compatibility between pymongo<>3.0.0.
import pymongo
from verlib2.distutils.version import LooseVersion
try:
    from pymongo import MongoClient as Connection
    from pymongo.read_preferences import ReadPreference
except ImportError:
    from pymongo.connection import Connection  # ty: ignore[import-not-found]

from pymongo.uri_parser import parse_uri
from pymongo import ASCENDING, DESCENDING

from gridfs import GridFS
from gridfs.errors import NoFile

import pickle
from urllib.parse import quote_plus

IS_PYMONGO3 = LooseVersion(pymongo.version) >= LooseVersion('3.0.0')


def _pop_slaveok(url):
    # pymongo 4 rejects a URL that has the legacy `slaveok` option.
    base, sep, query = url.partition('?')
    slaveok = False
    kept = []
    for part in query.replace(';', '&').split('&'):
        name, _, value = part.partition('=')
        if name.lower() == 'slaveok':
            slaveok = value.lower() in ('true', '1', 'yes')
        elif part:
            kept.append(part)
    if kept:
        base += '?' + '&'.join(kept)
    return base, slaveok

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

        self.url_database: str
        self.url_nodelist: List
        self.url_collection: str
        self.url_username: str
        self.url_password: str
        self.url_options: dict
        self.url_slaveok: str

        url, self.url_slaveok = _pop_slaveok(url)
        for k, v in parse_uri(url).items():
            setattr(self, "url_%s"%k, v)

        if not self.url_database or not self.url_nodelist:
            raise MissingCacheParameter("Invalid MongoDB url.")

        data_key = "mongodb_gridfs:%s:%s" % (self.url_database, self.url_collection)
        self.gridfs = MongoDBGridFSNamespaceManager.clients.get(
                        data_key, self._create_mongo_connection)

    def _create_mongo_connection(self):
        hosts = ",".join(["%s:%s" % h for h in self.url_nodelist])
        log.info("[MongoDBGridFS] Hosts: %s" % hosts)

        if self.url_username:
            log.info("[MongoDBGridFS] Authenticating as %s" % self.url_username)
            host_uri = 'mongodb://%s:%s@%s/%s' % (
                quote_plus(self.url_username),
                quote_plus(self.url_password or ''),
                hosts, self.url_database)
        else:
            host_uri = 'mongodb://%s' % hosts

        options = dict((k.lower(), v) for k, v in self.url_options.items())

        params: Dict[str, Any] = {}
        if self.url_slaveok:
            if IS_PYMONGO3:
                params['readPreference'] = 'secondaryPreferred'
            else:
                params['slaveok'] = True

        if "replicaset" in options:
            params['replicaset'] = options["replicaset"] or ""

        conn = Connection(host_uri, **params)
        db = conn[self.url_database]

        collection = db["%s.files" % self.url_collection]
        collection.create_index(
            [("namespace", ASCENDING), ("filename", ASCENDING)], unique=True)
        collection.create_index([("namespace", ASCENDING)])

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
        if IS_PYMONGO3:
            self.collection.delete_many({'namespace':self.namespace})
        else:
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
        except Exception as e:
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

    def set_value(self, key, value, expiretime=None):
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
