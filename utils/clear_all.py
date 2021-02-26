import os
from utils.keydb import KeyDB
from utils.logger import get_logger
from milvus import Milvus
from utils.mongo import MongoDatabaseWrapper

logger = get_logger('Clear All Tools')


search_client_params = {
    'host': os.environ.get('MILVUS_HOST', 'localhost'),
    'port': int(os.environ.get('MILVUS_PORT', 19530))
}


if __name__ == '__main__':
    milvus = Milvus(**search_client_params)
    a = milvus.drop_collection(os.environ.get('DB_COLLECTION_NAME', 'JFA_TEST'))
    logger.info('Drop milvus collection.')
    b = mongo = MongoDatabaseWrapper()
    c = mongo.drop_database()
    #mongo.collection.drop()
    #mongo = MongoDatabaseWrapper('registered_id')
    #mongo.collection.drop()
    logger.info(a)
    logger.info(b)
    logger.info(c)
    keydb = KeyDB(host=os.environ.get('KEYDB_HOST', 'localhost'),
                  port=os.environ.get('KEYDB_PORT', 6379),
                  password=os.environ.get('KEYDB_PASSWORD', ''))
    logger.info(keydb.keys())
    keydb.flushall()
    logger.info('Flush all data from keydb.')

