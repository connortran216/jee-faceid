import os
import cv2
import json
import base64
import pickle
import datetime
import numpy as np
from PIL import Image
from io import BytesIO
from kafka import KafkaConsumer
from utils.keydb import KeyDB
from core.search_client import SearchClient
from sklearn.metrics.pairwise import cosine_similarity
from kafka.consumer.subscription_state import ConsumerRebalanceListener

from utils.logger import get_logger
from utils.mongo import MongoDatabaseWrapper


logger = get_logger('JFA Face Updater')


class FaceUpdater:
    def __init__(self):
        super(FaceUpdater, self).__init__()

        self.consumer = KafkaConsumer(
            os.environ.get('KAFKA_UPDATER_TOPIC', 'UPDATER_QUEUE_'),
            bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9094'),
            group_id=os.environ.get('KAFKA_UPDATER_CONSUMER_GROUP', 'UPDATER_CONSUMER_'),
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

        self.keydb_cache_connector = KeyDB(
            host=os.environ.get('KEYDB_HOST', 'localhost'),
            port=os.environ.get('KEYDB_PORT', 6379),
            password=os.environ.get('KEYDB_PASSWORD', None),
            db=os.environ.get('KEYDB_CACHE_DB', 0)
        )

        self.mongo = MongoDatabaseWrapper()
        self.search_client = SearchClient()
        logger.info(f'[Mongo Database] {self.mongo}')

        self.number_keep_frame = int(os.environ.get('NUMBER_OF_KEEP_FRAME', 3))
        self.consumer.subscribe(topics=[os.environ.get('KAFKA_UPDATER_TOPIC', 'UPDATER_QUEUE_')],
                                listener=ConsumerRebalanceListener())

    @staticmethod
    def get_score(x, y):
        return float(cosine_similarity(x, y))

    def execute(self):
        self.consumer.poll()
        self.consumer.seek_to_end()
        logger.info('Listening...')

        for message in self.consumer:
            message = message.value

            session = message.get('session', None)
            if session is None:
                logger.warning('Received frame with none session')
                continue

            emp_id = message.get('employee_id', None)
            if emp_id is None:
                logger.warning('Received frame with none employee_id')
                continue

            company_id = message.get('company_id', None)
            if company_id is None:
                logger.warning('Received frame with none company_id')
                continue

            frame_id = message.get('frame_id', None)
            if frame_id is None:
                logger.warning('Received frame with none frame_id')
                continue

            frame = self.keydb_cache_connector.get(frame_id)
            if frame is None:
                logger.info(f'Can not read {frame_id} from cache database.')
                continue

            logger.info(f'Received 1 update request from {company_id} - {emp_id}')
            try:
                frame = Image.open(BytesIO(base64.b64decode(frame)))
            except Exception as ex:
                logger.info('Decode failed')
                logger.exception(ex)
                continue

            frame = np.array(frame)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            feat = self.keydb_verifier_buffer.get(session)
            feat = pickle.loads(feat)

            mongo_pos = self.mongo.get_collection(f'{company_id}')
            pivots = mongo_pos.find({'employee_id': emp_id})
            pivots = [pivot.get('_id') for pivot in pivots]
            status, comparable_vectors = self.search_client.get_batch(f'JFA_Company_{company_id}', pivots)

            if status.code == 0:
                comparable_vectors = np.array(comparable_vectors)
                current_n_frame = comparable_vectors.shape[0]
                logger.info(f'Number of current frame: {current_n_frame}')

                if current_n_frame >= self.number_keep_frame:
                    # delete most outdated frame
                    min_pos, min_score = -1, 10000
                    for idx, vector in enumerate(comparable_vectors):
                        vector = np.array(vector)
                        try:
                            _score = FaceUpdater.get_score(feat, vector.reshape(1, 512))
                            if _score < min_score:
                                min_score, min_pos = _score, idx
                        except Exception as ex:
                            logger.exception(ex)

                    delete_position = pivots[min_pos]

                    mongo_pos.delete_one({
                        '_id': delete_position,
                        'employee_id': emp_id
                    })

                    mongo_register_pool = self.mongo.get_collection(f'JFA_Company_{company_id}_register_buffer_pool')
                    mongo_register_pool.delete_one({
                        'employee_id': emp_id,
                        'company_id': company_id,
                        'pos': delete_position
                    })

                    self.search_client.delete_by_id(f'JFA_Company_{company_id}', delete_position)
                    logger.info(f'Delete one frame company id: {company_id} - employee id: {emp_id}')

                # after that, insert the new one
                feat = feat.tolist()
                status, ids = self.search_client.insert_batch(f'JFA_Company_{company_id}',
                                                              feat)

                if status.code == 0:
                    mongo_cursor = self.mongo.get_collection(f'{company_id}')
                    for pos_id in ids:
                        mongo_cursor.insert_one({
                            '_id': pos_id,
                            'employee_id': emp_id
                        })

                    r, v = cv2.imencode('.jpg', frame)
                    jpg_as_text = base64.b64encode(v)

                    register_buffer = self.mongo.get_collection(f'JFA_Company_{company_id}_register_buffer_pool')
                    register_buffer.insert_one({
                        'f_type': '_register_image_',
                        'employee_id': emp_id,
                        'company_id': company_id,
                        'date': str(datetime.datetime.now()),
                        'feature': None,
                        'face': jpg_as_text,
                        'pos': ids[0]
                    })

                    logger.info(f'Inserted 1 frames '
                                f'of employee {emp_id} of company '
                                f'{company_id}.')
                else:
                    logger.info(status)


face_updater = FaceUpdater()
face_updater.execute()
