import os
import json
import pickle
import datetime
import numpy as np
from kafka import KafkaConsumer
from kafka.consumer.subscription_state import ConsumerRebalanceListener
from utils.landmark import FacialLandmark, FacialLandmarkWarehouse
from core.search_client import SearchClient
from utils.logger import get_logger
from utils.keydb import KeyDB
from utils.mongo import MongoDatabaseWrapper

logger = get_logger('JFA Register Controller')
# os.environ['KAFKA_BOOTSTRAP_SERVERS'] = '192.168.2.160:9092'


class RegisterResponseHandler:
    def __init__(self):
        super(RegisterResponseHandler, self).__init__()

        self.consumer = KafkaConsumer(
            os.environ.get('KAFKA_REGISTER_RESPONSE_TOPIC', 'REGISTER_RESPONSE_'),
            bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9094'),
            group_id=os.environ.get('KAFKA_REGISTER_RESPONSE_CONSUMER_GROUP', 'REGISTER_RESPONSE_CONSUMER_'),
            auto_offset_reset='latest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            enable_auto_commit=True
        )

        self.keydb_cache_db = KeyDB(
            host=os.environ.get('KEYDB_HOST', 'localhost'),
            port=os.environ.get('KEYDB_PORT', 6379),
            password=os.environ.get('KEYDB_PASSWORD', None),
            db=os.environ.get('KEYDB_DONE_SESSION_DB', 0)
        )

        self.keydb_done_session = KeyDB(
            host=os.environ.get('KEYDB_HOST', 'localhost'),
            port=os.environ.get('KEYDB_PORT', 6379),
            password=os.environ.get('KEYDB_PASSWORD', None),
            db=os.environ.get('KEYDB_DONE_SESSION_DB', 3)
        )

        self.mongo = MongoDatabaseWrapper()
        self.warehouse = FacialLandmarkWarehouse()
        self.search_client = SearchClient()
        self.number_of_register_frame = int(os.environ.get('NUMBER_OF_REGISTER_FRAME', 20))
        self.consumer.subscribe(topics=[os.environ.get('KAFKA_REGISTER_RESPONSE_TOPIC', 'REGISTER_RESPONSE_')],
                                listener=ConsumerRebalanceListener())

    def execute(self):
        self.consumer.poll()
        self.consumer.seek_to_end()
        logger.info(f'Listening...')

        for message in self.consumer:
            message = message.value

            session = message.get('session', None)
            if session is None:
                continue

            session_done = self.keydb_done_session.get(session)
            if session_done is None or (session_done is not None and session_done.decode('utf-8') != '-1'):
                logger.warning('Session done. Skipped!')
                continue

            employee_id = message.get('employee_id', None)
            if employee_id is None:
                continue
            
            company_id = message.get('company_id', None)
            if company_id is None:
                continue

            frame_id = message.get('frame_id', None)
            if frame_id is None:
                logger.warn(f'Received frame from session {session} with none frame_id')
                continue

            f_type = message.get('f_type', None)
            if f_type is None:
                logger.warn(f'Received frame from session {session} with none f_type')
                continue

            lmrk = message.get('landmarks', None)
            if lmrk is None:
                continue

            logger.info(f'Received {frame_id} from {session}')

            facial_landmark = FacialLandmark(lmrk['a'], lmrk['b'], lmrk['c'], lmrk['d'], lmrk['e'])
            if not self.warehouse.contains(session, facial_landmark):
                self.warehouse.add(session, facial_landmark)

            if self.warehouse.__len__(session) >= self.number_of_register_frame \
                    and self.keydb_done_session.get(session).decode('utf-8') == '-1' :
                self.keydb_done_session.set(session, 'register_done', ex=os.environ.get('KEYDB_KEY_TTL', 600))
                # self.keydb_register_id.set(employee_id, 1)
                # mongo = MongoDatabaseWrapper(f'{company_id}_{registered}')

                mongo_cursor = self.mongo.get_collection(f'{company_id}_registered')
                mongo_cursor.insert_one({
                    '_id': employee_id,
                    'registered': datetime.datetime.now(),
                    'last_update': datetime.datetime.now(),
                    'last_score': 0.0
                })

                mongo_cursor = self.mongo.get_collection(f'JFA_Companies')
                if mongo_cursor.find_one({ '_id': company_id }) is None:
                    mongo_cursor.insert_one({
                        '_id': company_id,
                        'registered': datetime.datetime.now()
                    })

                register_buffer = self.mongo.get_collection(f'JFA_Company_{company_id}_register_buffer_pool')
                records = register_buffer.find({
                    'employee_id': employee_id,
                    'company_id': company_id
                })

                features = list()
                for record in records:
                    feature = pickle.loads(record.get('feature')).tolist()[0]
                    features.append(feature)

                status, ids = self.search_client.insert_batch(f'JFA_Company_{company_id}',
                                                              features)

                if status.code == 0:
                    mongo_cursor = self.mongo.get_collection(f'{company_id}')
                    for pos_id in ids:
                        mongo_cursor.insert_one({
                            '_id': pos_id,
                            'employee_id': employee_id
                        })
                    logger.info(f'Inserted {features.__len__()} frames '
                                f'of employee {employee_id} of company '
                                f'{company_id}.')

                logger.info(f'Denied {session}')


register_response_handler = RegisterResponseHandler()
register_response_handler.execute()
