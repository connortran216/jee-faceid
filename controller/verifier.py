import os
import json
import pickle
import numpy as np
from utils.keydb import KeyDB
from utils.logger import get_logger
from kafka import KafkaProducer, KafkaConsumer
from core.search_client import SearchClient
from utils.mongo import MongoDatabaseWrapper
from sklearn.metrics.pairwise import cosine_similarity
from kafka.consumer.subscription_state import ConsumerRebalanceListener

logger = get_logger('JFA Face Verifier')


class UPDATER:
    Enable = False


class FaceVerifier:
    def __init__(self):
        super(FaceVerifier, self).__init__()

        self.producer = KafkaProducer(
            bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9094'),
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        self.consumer = KafkaConsumer(
            os.environ.get('KAFKA_VERIFIER_RESPONSE_TOPIC', 'VERIFIER_RESPONSE_'),
            bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9094'),
            group_id=os.environ.get('KAFKA_VERIFIER_CONSUMER_GROUP', 'VERIFIER_CONSUMER_'),
            auto_offset_reset='latest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            enable_auto_commit=True
        )

        self.keydb_verifier_buffer = KeyDB(
                host=os.environ.get('KEYDB_HOST', 'localhost'),
            port=os.environ.get('KEYDB_PORT', 6379),
            password=os.environ.get('KEYDB_PASSWORD', None),
            db=os.environ.get('KEYDB_VERIFIER_BUFFER', 7)
        )

        self.keydb_done_session = KeyDB(
            host=os.environ.get('KEYDB_HOST', 'localhost'),
            port=os.environ.get('KEYDB_PORT', 6379),
            password=os.environ.get('KEYDB_PASSWORD', None),
            db=os.environ.get('KEYDB_DONE_SESSION_DB', 3)
        )

        self.keydb_verifier_query_cache = KeyDB(
            host=os.environ.get('KEYDB_HOST', 'localhost'),
            port=os.environ.get('KEYDB_PORT', 6379),
            password=os.environ.get('KEYDB_PASSWORD', None),
            db=os.environ.get('KEYDB_VERIFIER_QUERY_CACHE_DB', 8)
        )

        self.search_client = SearchClient()
        self.mongo = MongoDatabaseWrapper()
        self.updater_topic = os.environ.get('KAFKA_UPDATER_TOPIC', 'UPDATER_QUEUE_')
        self.confidence_frame = float(os.environ.get('NUMBER_OF_VERIFIER_CONFIDENCE_FRAME', 3))
        self.min_confidence = float(os.environ.get('VERIFIER_MIN_THRESHOLD', 0.3))
        self.max_confidence = float(os.environ.get('VERIFIER_MAX_THRESHOLD', 0.7))
        self.mean_confidence = float(os.environ.get('VERIFIER_MEAN_THRESHOLD', 0.4))
        self.mean_confidence = 0.4
        self.consumer.subscribe(topics=[os.environ.get('KAFKA_VERIFIER_RESPONSE_TOPIC', 'VERIFIER_RESPONSE_')],
                                listener=ConsumerRebalanceListener())

    @staticmethod
    def get_score(x, y):
        return float(cosine_similarity(x, y))

    def send_to_updater(self, session, company_id, employee_id, frame_id):
        self.producer.send(self.updater_topic,
                           {
                               'session': session,
                               'frame_id': frame_id,
                               'company_id': company_id,
                               'employee_id': employee_id
                           })
        logger.info(f'Sent 1 frame to {self.updater_topic}')

    def execute(self):
        self.consumer.poll()
        self.consumer.seek_to_end()
        logger.info(f'Listening..')

        for message in self.consumer:
            message = message.value

            session = message.get('session', None)
            if session is None:
                logger.info(f'[SKIPPED] Received message with none session')
                continue

            session_done = self.keydb_done_session.get(session)
            if session_done is None or (session_done is not None and session_done.decode('utf-8') != '-1'):
                logger.warning('Session done. Skipped!')
                continue

            frame_id = message.get('frame_id', None)
            if frame_id is None:
                logger.info('[SKIPPED] Received message with none frame_id')
                continue

            company_id = message.get('company_id', None)
            if company_id is None:
                logger.info('[SKIPPED] Received message with none company_id')
                continue

            employee_id = message.get('employee_id', None)
            if employee_id is None:
                logger.info('[SKIPPED] Received message with none employee_id')
                continue

            feature = self.keydb_verifier_buffer.get(session)
            feature = pickle.loads(feature)

            logger.info(f'Received query {frame_id}-{session}-{employee_id}-{company_id}')

            mongo_cursor = self.mongo.get_collection(f'{company_id}')
            pivots = mongo_cursor.find({ 'employee_id': employee_id })
            pivots = [pivot.get('_id') for pivot in pivots]
            status, comparable_vectors = self.search_client.get_batch(f'JFA_Company_{company_id}', pivots)
            
            if status.code == 0:
                comparable_vectors = np.array(comparable_vectors)
                for idx, vector in enumerate(comparable_vectors):
                    vector = np.array(vector)
                    try:
                        # logger.info(vector.shape)
                        _score = FaceVerifier.get_score(feature, vector.reshape(1, 512))
                    except Exception as ex:
                        logger.exception(ex)
                        continue

                    logger.info(f'Score {employee_id}-{frame_id} vs {pivots[idx]}: {_score}')
                    if _score < self.min_confidence:
                        continue
                    elif _score > self.max_confidence:
                        self.keydb_done_session.set(session, employee_id, ex=os.environ.get('KEYDB_KEY_TTL', 600))
                        if UPDATER.Enable is True:
                            self.send_to_updater(session=session,
                                                 company_id=company_id,
                                                 employee_id=employee_id,
                                                 frame_id=frame_id)
                        logger.info(f'[MATCHING] - Notify to application with returned_id: {employee_id} - {_score}')
                        break

                    _cnt = self.keydb_verifier_query_cache.get(session)
                    if _cnt is None:
                        self.keydb_verifier_query_cache.set(session, 1, ex=os.environ.get('KEYDB_KEY_TTL', 600))
                    else:
                        _cnt = int(_cnt) + 1
                        if _cnt >= self.confidence_frame:
                            self.keydb_done_session.set(session, employee_id, ex=os.environ.get('KEYDB_KEY_TTL', 600))
                            if UPDATER.Enable is True:
                                self.send_to_updater(session=session,
                                                     company_id=company_id,
                                                     employee_id=employee_id,
                                                     frame_id=frame_id)
                            logger.info(f'[MATCHING] - Notify to application with returned_id: {employee_id} - {_score}')
                            break
                        else:
                            self.keydb_verifier_query_cache.set(session, _cnt, ex=os.environ.get('KEYDB_KEY_TTL', 600))


face_verifier = FaceVerifier()
face_verifier.execute()
