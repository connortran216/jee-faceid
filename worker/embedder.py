import os
import cv2
import json
import pickle
import base64
import datetime
import numpy as np
from PIL import Image
from io import BytesIO
from bson import Binary
from utils.keydb import KeyDB
from utils.logger import get_logger
from core.v2.embed.embedder import FaceEmbedder
from core.search_client import SearchClient
from utils.mongo import MongoDatabaseWrapper
from kafka import KafkaProducer, KafkaConsumer
from kafka.consumer.subscription_state import ConsumerRebalanceListener

# os.environ['CUDA_VISIBLE_DEVICES'] = '1'
# os.environ['KAFKA_BOOTSTRAP_SERVERS'] = '192.168.2.160:9092'
logger = get_logger('JFA Face Embedder')


class EmbedderConsumer:
    def __init__(self):
        super(EmbedderConsumer, self).__init__()

        self.producer = KafkaProducer(
            bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9094'),
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        self.consumer = KafkaConsumer(
            os.environ.get('KAFKA_EMBEDDER_TOPIC', 'EMBEDDER_QUEUE_'),
            bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9094'),
            group_id=os.environ.get('KAFKA_EMBEDDER_CONSUMER_GROUP', 'EMBEDDER_CONSUMER_'),
            auto_offset_reset='latest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            enable_auto_commit=True
        )

        self.keydb_cache_connector = KeyDB(
            host=os.environ.get('KEYDB_HOST', 'localhost'),
            port=os.environ.get('KEYDB_PORT', 6379),
            password=os.environ.get('KEYDB_PASSWORD', None),
            db=os.environ.get('KEYDB_CACHE_DB', 0)
        )

        self.mongo = MongoDatabaseWrapper()
        logger.info(f'[Mongo Database] {self.mongo}')

        self.keydb_done_session = KeyDB(
            host=os.environ.get('KEYDB_HOST', 'localhost'),
            port=os.environ.get('KEYDB_PORT', 6379),
            password=os.environ.get('KEYDB_PASSWORD', None),
            db=os.environ.get('KEYDB_DONE_SESSION_DB', 3)
        )

        self.keydb_count_session = KeyDB(
            host=os.environ.get('KEYDB_HOST', 'localhost'),
            port=os.environ.get('KEYDB_PORT', 6379),
            password=os.environ.get('KEYDB_PASSWORD', None),
            db=os.environ.get('KEYDB_COUNT_SESSION_FRAME', 5)
        )

        self.keydb_register_buffer_cache = KeyDB(
            host=os.environ.get('KEYDB_HOST', 'localhost'),
            port=os.environ.get('KEYDB_PORT', 6379),
            password=os.environ.get('KEYDB_PASSWORD', None),
            db=os.environ.get('KEYDB_REGISTER_BUFFER', 6)
        )

        self.keydb_verifier_buffer = KeyDB(
            host=os.environ.get('KEYDB_HOST', 'localhost'),
            port=os.environ.get('KEYDB_PORT', 6379),
            password=os.environ.get('KEYDB_PASSWORD', None),
            db=os.environ.get('KEYDB_VERIFIER_BUFFER', 7)
        )

        self.recognizer_response_topic = os.environ.get('KAFKA_RECOGNIZER_RESPONSE_TOPIC', 'RECOGNIZER_RESPONSE_')
        self.verifier_response_topic = os.environ.get('KAFKA_VERIFIER_RESPONSE_TOPIC', 'VERIFIER_RESPONSE_')
        self.number_of_query_frame = int(os.environ.get('NUMBER_OF_QUERY_FRAME', 5))
        self.search_client = SearchClient()
        self.face_embedder = FaceEmbedder(os.path.join('static', 'embedder_resnet50_asia.pth'))
        self.consumer.subscribe(topics=[os.environ.get('KAFKA_EMBEDDER_TOPIC', 'EMBEDDER_QUEUE_')],
                                listener=ConsumerRebalanceListener())

    def execute(self):
        self.consumer.poll()
        self.consumer.seek_to_end()
        logger.info('Listening..')

        for message in self.consumer:
            message = message.value

            session = message.get('session', None)
            if session is None:
                logger.warning('Received frame with none session')
                continue

            session_done = self.keydb_done_session.get(session)
            if session_done is None or (session_done is not None and session_done.decode('utf-8') != '-1'):
                logger.warning('Session done. Skipped!')
                continue

            frame_id = message.get('frame_id', None)
            if frame_id is None:
                logger.warn(f'Received frame from session {session} with none frame_id')
                continue
            
            company_id = message.get('company_id', None)
            if company_id is None:
                logger.warn(f'Received frame from session {session} with none company_id')
                continue

            f_type = message.get('f_type', None)
            if f_type is None:
                logger.warn(f'Received frame from session {session} with none f_type')
                continue

            logger.info(f'Received message {frame_id} from {session}')

            frame = self.keydb_cache_connector.get(frame_id)
            if frame is None:
                logger.info(f'Can not read {frame_id} from cache database.')
                continue

            try:
                frame = Image.open(BytesIO(base64.b64decode(frame)))
            except Exception as ex:
                logger.info('Decode failed')
                logger.exception(ex)
                continue

            frame = np.array(frame)
            feat = self.face_embedder.get_features([frame])
            # logger.info(f'[LOGGER] Feature shape: {feat.shape}')

            if f_type == 'register':
                employee_id = message.get('employee_id', None)
                if employee_id is None:
                    logger.warn(f'Received frame from session {session} with none id')
                    continue

                # position_id = self.search_client.insert_one(f'JFA_Company_{company_id}', feat)
                # mongo_cursor = self.mongo.get_collection(f'{company_id}')
                # mongo_cursor.insert_one({ '_id': position_id, 'employee_id': employee_id })

                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                r, v = cv2.imencode('.jpg', frame)
                jpg_as_text = base64.b64encode('.jpg', v)

                register_buffer = self.mongo.get_collection(f'JFA_Company_{company_id}_register_buffer_pool')
                register_buffer.insert_one({
                    'f_type': 'register',
                    'employee_id': employee_id,
                    'company_id': company_id,
                    'date': str(datetime.datetime.now()),
                    'feature': Binary(pickle.dumps(feat, protocol=2), subtype=128),
                    'face': jpg_as_text
                })

                logger.info(f'[BUFFER] Insert {frame_id} of {employee_id} into {company_id}')

            elif f_type == 'register_image':
                employee_id = message.get('employee_id', None)
                if employee_id is None:
                    logger.warn(f'Received frame from session {session} with none id')
                    continue

                feat = feat.tolist()
                status, ids = self.search_client.insert_batch(f'JFA_Company_{company_id}',
                                                              feat)

                if status.code == 0:
                    mongo_cursor = self.mongo.get_collection(f'{company_id}_registered')
                    mongo_cursor.insert_one({'_id': employee_id, 'registered': 1})

                    mongo_cursor = self.mongo.get_collection(f'JFA_Companies')
                    if mongo_cursor.find_one({'_id': company_id}) is None:
                        mongo_cursor.insert_one({'_id': company_id, 'registered': datetime.datetime.now()})

                    mongo_cursor = self.mongo.get_collection(f'{company_id}')
                    for pos_id in ids:
                        mongo_cursor.insert_one({
                            '_id': pos_id,
                            'employee_id': employee_id
                        })

                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    r, v = cv2.imencode('.jpg', frame)
                    jpg_as_text = base64.b64encode(v)

                    register_buffer = self.mongo.get_collection(f'JFA_Company_{company_id}_register_buffer_pool')
                    register_buffer.insert_one({
                        'f_type': '_register_image_',
                        'employee_id': employee_id,
                        'company_id': company_id,
                        'date': str(datetime.datetime.now()),
                        'feature': None,
                        'face': jpg_as_text,
                        'pos': ids[0]
                    })

                    logger.info(f'Inserted 1 frames '
                                f'of employee {employee_id} of company '
                                f'{company_id}.')
                else:
                    logger.info(f'Failed register image {company_id} - {employee_id}')
                continue

            elif f_type == 'recognizer' or f_type == 'verifier':
                _count_session = self.keydb_count_session.get(session)
                if _count_session is None:
                    self.keydb_count_session.set(session, 1, ex=os.environ.get('KEYDB_KEY_TTL', 600))
                elif int(_count_session) > self.number_of_query_frame:
                    self.keydb_done_session.set(session, 0)
                    logger.info(f'{session} timed out.')
                    continue
                else:
                    self.keydb_count_session.set(session, int(_count_session) + 1)

                self.keydb_cache_connector.set(f'{session}_register_status',
                                               'done',
                                               ex=os.environ.get('KEYDB_KEY_TTL, 600'))
                self.keydb_verifier_buffer.set(session,
                                               Binary(pickle.dumps(feat, protocol=2), subtype=128),
                                               ex=os.environ.get('KEYDB_KEY_TTL', 600))

                if f_type == 'recognizer':
                    candidates = self.search_client.search(f'JFA_Company_{company_id}', feat)

                    if candidates is None:
                        logger.info(f'[SKIPPED] No candidates for this frame {frame_id}')
                        continue

                    if candidates.__len__() == 0:
                        continue

                    results = list()
                    mongo_cursor = self.mongo.get_collection(f'{company_id}')

                    for candidate in candidates[0]:
                        emp_id = mongo_cursor.find_one({ '_id': candidate.id })

                        if emp_id is None:
                            continue

                        if 'employee_id' in emp_id:
                            emp_id = emp_id['employee_id']
                        else:
                            emp_id = None

                        if emp_id is None:
                            continue

                        results.append([emp_id, candidate.distance])

                    self.producer.send(
                        self.recognizer_response_topic,
                        {
                            'session': session,
                            'frame_id': frame_id,
                            'company_id': company_id,
                            'query_results': results
                        }
                    )

                    logger.info(f'Sent query results of {frame_id} to {self.recognizer_response_topic}')

                elif f_type == 'verifier':
                    employee_id = message.get('employee_id', None)
                    if employee_id is None:
                        logger.warn(f'Received frame from session {session} with none id')
                        continue

                    self.producer.send(
                        self.verifier_response_topic,
                        {
                            'session': session,
                            'frame_id': frame_id,
                            'company_id': company_id,
                            'employee_id': employee_id
                        }
                    )

                    logger.info(f'Sent vector of {frame_id} to {self.verifier_response_topic}')

        self.consumer.close()


embedder_consumer = EmbedderConsumer()
embedder_consumer.execute()
