import os
from pymongo import MongoClient


class MongoDatabaseWrapper(object):
    def __init__(self):
        super(MongoDatabaseWrapper, self).__init__()
        self.connector = MongoClient('mongodb://{}:{}@{}:{}'.format(
            os.environ.get('MONGODB_USER', 'dps'),
            os.environ.get('MONGODB_PASSWORD', 'dps123'),
            os.environ.get('MONGODB_HOST', 'mongo'), #TODO: why can not get env
            os.environ.get('MONGODB_PORT', '27017')
        ))

        self.database = self.connector[os.environ.get('MONGODB_DATABASE', 'JFA')]
        # self.collection = self.database[collection]
    
    def get_collection(self, collection):
        return self.database[collection]

    def __str__(self):
        return repr(self.connector)

    def drop_database(self, database=os.environ.get('MONGODB_DATABASE', 'JFA')):
        self.connector.drop_database(database)
