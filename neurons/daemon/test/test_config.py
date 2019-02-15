
import unittest

import yaml

from neurons.daemon import ServiceDaemon
from neurons import __version__ as NEURONS_VERSION

TEST_CONFIG = """
SomeClass:
    daemonize: false
    loggers:
    -   Logger:
            level: DEBUG
            path: .
    main_store: sql_main
    name: somedaemon
    secret: c29tZSBzZWNyZXQ=
    services:
    -   HttpServer:
            type: tcp4
            host: 0.0.0.0
            name: someservice
            port: 7001
            subapps:
            -   StaticFileServer:
                    disallowed_exts: []
                    list_contents: false
                    path: /home/plq/src/github/plq/neurons/assets
                    url: assets
    stores:
    -   Relational:
            async_pool: true
            backend: sqlalchemy
            conn_str: postgresql://postgres:@localhost:5432/somedaemon_plq
            echo_pool: false
            max_overflow: 3
            name: sql_main
            pool_recycle: 3600
            pool_size: 10
            pool_timeout: 30
            sync_pool: true
            sync_pool_type: QueuePool
    uuid: deac2096-0e18-11e6-a294-5453edabe249
"""


class TestConfig(unittest.TestCase):
    def test_migrate_versionless_to_versioned(self):
        ret = ServiceDaemon()._migrate_impl(TEST_CONFIG)
        retd = yaml.load(ret)
        key, = retd.keys()

        store = iter(retd.values()).next()['stores'][0]
        assert not ('Relational' in store)
        assert 'RelationalStore' in store
        assert len(retd) == 1
        assert retd[key]['file-version'] == NEURONS_VERSION

    def test_uidgid(self):
        config = ServiceDaemon.parse_config_string(TEST_CONFIG, "test")
        assert config.get_gid() == -1
        assert config.get_uid() == -1

        config.gid = "root"
        assert config.get_gid() == 0

        config.uid = "root"
        assert config.get_uid() == 0


if __name__ == '__main__':
    unittest.main()
