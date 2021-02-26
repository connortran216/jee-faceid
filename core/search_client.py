import os
import numpy as np

from utils.database import DatabaseConnector
from utils.logger import get_logger, ignore_runtime_error
from milvus import Milvus, MetricType, IndexType

logger = get_logger(logger_name='JFA Search Client')

search_client_params = {
    'host': os.environ.get('MILVUS_HOST', 'localhost'),
    'port': int(os.environ.get('MILVUS_PORT', 19530))
}

search_collection_params = {
    'collection_name': os.environ.get('DB_COLLECTION_NAME', 'JFA_TEST'),
    'dimension': 512,
    'index_file_size': 2048,
    'metric_type': MetricType.IP
}

_search_params = {
    'nprobe': 16
}


class SearchClient(DatabaseConnector):
    def __init__(self, *args, **kwargs):
        super(SearchClient, self).__init__()
        self.collection_name = os.environ.get('DB_COLLECTION_NAME', 'JFA_TEST')
        
        try:
            self.cursor = Milvus(**search_client_params)
            logger.info(f'Connection status: {self.cursor.server_status()}')
        except Exception as ex:
            self.cursor = None
            logger.info('Can not connect to milvus server')
            logger.exception(ex)

        # self.create_collection()
        # self.create_index(self.collection_name)
        # self.top_k_similar = int(os.environ.get('TOP_K_SIMILAR', 3)) #TODO: what the heck is it?
        self.top_k_similar = 3

    @staticmethod
    def normalize(x):
        return x / np.sqrt(np.sum((x ** 2), keepdims=True, axis=1))

    @ignore_runtime_error
    def create_collection(self, *args, **kwargs):
        if not self.cursor.has_collection(self.collection_name)[1]:
            self.cursor.create_collection(search_collection_params)
        else:
            logger.warn(f'Collection is existed!')

    @ignore_runtime_error
    def drop_collection(self, *args, **kwargs):
        if self.cursor.has_collection(self.collection_name)[1]:
            self.cursor.drop_collection(self.collection_name)

    @ignore_runtime_error
    def create_index(self, collection, *args, **kwargs):
        status = self.cursor.create_index(
            collection,
            IndexType.IVFFLAT,
            {
                'nlist': 2048
            }
        )
        if status.code == 0:
            logger.info('Create index successfully')
        else:
            logger.warn('Failed to create index')
    
    @ignore_runtime_error
    def delete_by_id(self, collection, id, *args, **kwargs):
        status = self.cursor.delete_entity_by_id(collection, [id])
        logger.info(status)

    @ignore_runtime_error
    def insert_one(self, collection, v_val, *args, **kwargs):
        # print(collection)

        if not self.cursor.has_collection(collection)[1]:
            _collection_params = {
                'collection_name': collection,
                'dimension': 512,
                'index_file_size': 2048,
                'metric_type': MetricType.IP
            }
            
            self.cursor.create_collection(_collection_params)
            
            self.cursor.create_index(collection, IndexType.FLAT, { 'nlist': 2048})

        status, id = self.cursor.insert(
            collection_name=collection,
            records=v_val,
        )
        logger.info(f'Inserted {id[0]} into {collection}')
        return id[0]

    @ignore_runtime_error
    def insert_batch(self, collection, v_vals, *args, **kwargs):
        if not self.cursor.has_collection(collection)[1]:
            _collection_params = {
                'collection_name': collection,
                'dimension': 512,
                'index_file_size': 2048,
                'metric_type': MetricType.IP
            }

            self.cursor.create_collection(_collection_params)
            self.cursor.create_index(collection, IndexType.FLAT, {'nlist': 2048})

        status, id = self.cursor.insert(
            collection_name=collection,
            records=v_vals,
        )

        return status, id

    @ignore_runtime_error
    def get_one(self, id, *args, **kwargs):
        status, vector = self.cursor.get_entity_by_id(
            collection_name=self.collection_name,
            ids=[id]
        )
        logger.info(f'Get {status}')
        return status, vector

    @ignore_runtime_error
    def get_batch(self, collection, ids, *args, **kwargs):
        status, vector = self.cursor.get_entity_by_id(
            collection_name=collection,
            ids=ids
        )
        logger.info(f'Get {status}')
        return status, vector

    @ignore_runtime_error
    def search(self, collection, query_vector, *args, **kwargs):
        search_params = {
            'collection_name': collection,
            'query_records': SearchClient.normalize(query_vector),
            'top_k': self.top_k_similar,
            'params': _search_params
        }

        status, results = self.cursor.search(**search_params)
        if status.OK():
            return results


# if __name__ == '__main__':
#     search_client = SearchClient()

# import random
# vectors = [[random.random() for _ in range(1028)] for __ in range(100)]
# ids = [_ for _ in range(100)]

# search_client.insert_batch(ids, vectors)
# search_client.get_one(99)
