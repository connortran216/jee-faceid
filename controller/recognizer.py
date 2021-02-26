import os
import json
from kafka import KafkaProducer, KafkaConsumer
from utils.logger import get_logger
from utils.keydb import KeyDB
from utils.mongo import MongoDatabaseWrapper
from kafka.consumer.subscription_state import ConsumerRebalanceListener

logger = get_logger('JFA Recognizer Controller')
# os.environ['KAFKA_BOOTSTRAP_SERVERS'] = '192.168.2.160:9092'


class UPDATER:
    Enable = False


class RecognizerResponseHandler:
    def __init__(self):
        super(RecognizerResponseHandler, self).__init__()
        self.mongo = MongoDatabaseWrapper()

        self.producer = KafkaProducer(
            bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9094'),
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        self.consumer = KafkaConsumer(
            os.environ.get('KAFKA_RECOGNIZER_RESPONSE_TOPIC', 'RECOGNIZER_RESPONSE_'),
            bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9094'),
            group_id=os.environ.get('KAFKA_RECOGNIZER_RESPONSE_CONSUMER_GROUP', 'RECOGNIZER_RESPONSE_CONSUMER_'),
            auto_offset_reset='latest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            enable_auto_commit=True
        )

        self.keydb_done_session = KeyDB(
            host=os.environ.get('KEYDB_HOST', 'localhost'),
            port=os.environ.get('KEYDB_PORT', 6379),
            password=os.environ.get('KEYDB_PASSWORD', None),
            db=os.environ.get('KEYDB_DONE_SESSION_DB', 3)
        )

        self.keydb_query_cache = KeyDB(
            host=os.environ.get('KEYDB_HOST', 'localhost'),
            port=os.environ.get('KEYDB_PORT', 6379),
            password=os.environ.get('KEYDB_PASSWORD', None),
            db=os.environ.get('KEYDB_QUERY_CACHE', 4)
        )

        self.top_k_similar = int(os.environ.get('TOP_K_SIMILAR', 3))
        self.updater_topic = os.environ.get('KAFKA_UPDATER_TOPIC', 'UPDATER_QUEUE_')
        self.confidence_frame = int(os.environ.get('NUMBER_OF_RECOGNIZER_CONFIDENCE_FRAME', 4))
        self.confidence_threshold = float(os.environ.get('RECOGNIZER_MEAN_THRESHOLD', 0.4))
        self.confidence_threshold = 0.4
        self.min_confidence_threshold = float(os.environ.get('RECOGNIZER_MIN_THRESHOLD', 0.5))
        self.max_confidence_threshold = float(os.environ.get('RECOGNIZER_MAX_THRESHOLD', 0.7))
        self.consumer.subscribe(topics=[os.environ.get('KAFKA_RECOGNIZER_RESPONSE_TOPIC', 'RECOGNIZER_RESPONSE_')],
                                listener=ConsumerRebalanceListener())

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
        logger.info(f'Listening... with CONFIDENCE_THRESHOLD={self.confidence_threshold}')

        for message in self.consumer:
            message = message.value

            session = message.get('session', None)
            if session is None:
                continue

            session_done = self.keydb_done_session.get(session)
            if session_done is None or (session_done is not None and session_done.decode('utf-8') != '-1'):
                logger.warning('Session done. Skipped!')
                continue

            frame_id = message.get('frame_id', None)
            if frame_id is None:
                continue
            
            company_id = message.get('company_id', None)
            if company_id is None:
                continue

            logger.info(f'Received {frame_id}')

            query_results = message.get('query_results')
            if query_results is None:
                continue

            logger.info(f'query results: {query_results}')
            for result in query_results:
                if float(result[1]) < self.confidence_threshold:
                    continue

                if float(result[1]) > self.max_confidence_threshold:
                    self.keydb_done_session.set(session, result[0], ex=os.environ.get('KEYDB_KEY_TTL', 600))
                    logger.info(f'Notify to application with returned_id: {result[0]} - {result[1]}')
                    if UPDATER.Enable is True:
                        self.send_to_updater(session=session,
                                             company_id=company_id,
                                             employee_id=result[0],
                                             frame_id=frame_id)
                    break

                _cnt = self.keydb_query_cache.get(f'{session}_{result[0]}')
                if _cnt is None:
                    self.keydb_query_cache.set(f'{session}_{result[0]}', 1, ex=os.environ.get('KEYDB_KEY_TTL', 600))
                else:
                    _cnt = int(_cnt) + 1
                    if _cnt >= self.confidence_frame:
                        self.keydb_done_session.set(session, result[0], ex=os.environ.get('KEYDB_KEY_TTL', 600))
                        logger.info(f'Notify to application with returned_id: {result[0]} - {result[1]}')
                        if UPDATER.Enable is True:
                            self.send_to_updater(session=session,
                                                 company_id=company_id,
                                                 employee_id=result[0],
                                                 frame_id=frame_id)
                        break
                    else:
                        self.keydb_query_cache.set(f'{session}_{result[0]}', _cnt, ex=os.environ.get('KEYDB_KEY_TTL', 600))


recognizer_response_handler = RecognizerResponseHandler()
recognizer_response_handler.execute()
