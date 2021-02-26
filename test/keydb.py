import pickle
import unittest
from redis import StrictRedis


class KeyDBTestCase(unittest.TestCase):
    def test_keydb_connector(self):
        connector = StrictRedis(
            host='localhost',
            port=6379,
            db=9
        )


    def test_list_insert(self):
        connector = StrictRedis(
            host='localhost',
            port=6379,
            db=10
        )

        connector.lpush('d', 1)
        # connector.set('a', '1')
        for i in range(connector.llen('d')):
            # print(connector.lindex('d', i))
            self.assertIsNotNone(connector.lindex('d', i))

unittest.main()
