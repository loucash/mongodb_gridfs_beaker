import logging

from unittest import mock

import pymongo
import pytest

import mongodb_gridfs_beaker
from mongodb_gridfs_beaker import MongoDBGridFSNamespaceManager, _pop_slaveok


@pytest.fixture
def connect(tmp_path):
    counter = [0]

    def _connect(url_template):
        # Clients are cached per database and collection.
        counter[0] += 1
        url = url_template % ('test.conn%d_%s' % (counter[0], tmp_path.name))
        MongoDBGridFSNamespaceManager('ns', url=url, lock_dir=str(tmp_path))
        return client

    with mock.patch.object(mongodb_gridfs_beaker, 'Connection') as client, \
            mock.patch.object(mongodb_gridfs_beaker, 'GridFS'):
        yield _connect


def test_plain_url(connect):
    client = connect('mongodb://localhost/%s')
    client.assert_called_once_with('mongodb://localhost:27017')


def test_credentials_go_into_client_uri(connect):
    client = connect('mongodb://us%%40er:p%%2Fw%%2Bd@localhost:27017/%s')
    client.assert_called_once_with('mongodb://us%40er:p%2Fw%2Bd@localhost:27017/test')
    client.return_value.__getitem__.return_value.authenticate.assert_not_called()


def test_password_is_not_logged(connect, caplog):
    with caplog.at_level(logging.DEBUG, logger='mongodb_gridfs_beaker'):
        connect('mongodb://user:s3cret@localhost/%s')
    assert 'user' in caplog.text
    assert 's3cret' not in caplog.text


def test_slaveok(connect):
    client = connect('mongodb://localhost/%s?slaveok=true')
    client.assert_called_once_with(
        'mongodb://localhost:27017',
        readPreference='secondaryPreferred')


def test_slaveok_false(connect):
    client = connect('mongodb://localhost/%s?slaveOk=false')
    client.assert_called_once_with('mongodb://localhost:27017')


def test_replicaset(connect):
    client = connect('mongodb://host1,host2:27018/%s?replicaSet=rs0')
    client.assert_called_once_with(
        'mongodb://host1:27017,host2:27018', replicaset='rs0')


def test_slaveok_and_replicaset(connect):
    client = connect('mongodb://localhost/%s?slaveok=true&replicaSet=rs0')
    client.assert_called_once_with(
        'mongodb://localhost:27017',
        readPreference='secondaryPreferred', replicaset='rs0')


@pytest.mark.parametrize('url, expected', [
    ('mongodb://h/db.c', ('mongodb://h/db.c', False)),
    ('mongodb://h/db.c?slaveok=true', ('mongodb://h/db.c', True)),
    ('mongodb://h/db.c?slaveOk=1&replicaSet=rs0', ('mongodb://h/db.c?replicaSet=rs0', True)),
    ('mongodb://h/db.c?replicaSet=rs0;slaveok=false', ('mongodb://h/db.c?replicaSet=rs0', False)),
])
def test_pop_slaveok(url, expected):
    assert _pop_slaveok(url) == expected


def test_client_accepts_the_arguments():
    client = pymongo.MongoClient(
        'mongodb://us%40er:p%2Fw%2Bd@localhost:27017/test',
        readPreference='secondaryPreferred', replicaset='rs0', connect=False)
    assert client.read_preference.mongos_mode == 'secondaryPreferred'
