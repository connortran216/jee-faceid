import os
import cv2
import sys
import json
import base64
import pickle
import numpy as np
from bson import Binary
from PIL import Image
from io import BytesIO
from utils.keydb import KeyDB
from utils.logger import get_logger
from core.detector import FaceDetector
from utils.landmark import FacialLandmark
from kafka import KafkaConsumer, KafkaProducer
from kafka.consumer.subscription_state import ConsumerRebalanceListener

# os.environ['CUDA_VISIBLE_DEVICES'] = '1'
# os.environ['KAFKA_BOOTSTRAP_SERVERS'] = '192.168.2.160:9092'

logger = get_logger('JFA Face Detector')


class DetectorConsumer:
    """
    Face Detector Consumer: Detecting face and send to other queue
    in order to further process.
    - Receive request from KAFKA_DETECTOR_QUEUE. Request format:
    {
        "session": <working session>,
        "frame": <base64 image>,
        "employee_id": <id of employee>,
        "f_type": <"register" or "recognizer">
    }
    - Detect face from request frame.
    - Send detected face to KAFKA_EMBEDDER_QUEUE.
    {
        "session": <working session>,
        "employee_id": <id of employee>,
        "landmarks": <facial landmarks of detected face>,
        "frame_id": <id of request frame>,
        "f_type": <"register" or "recognizer">
    }
    """

    def __init__(self):
        super(DetectorConsumer, self).__init__()

        # kafka producer
        self.producer = KafkaProducer(
            bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9094'),
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        # kafka consumer
        self.consumer = KafkaConsumer(
            os.environ.get('KAFKA_DETECTOR_TOPIC', 'DETECTOR_QUEUE_'),
            bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9094'),
            group_id=os.environ.get('KAFKA_DETECTOR_CONSUMER_GROUP', 'DETECTOR_CONSUMER_'),
            auto_offset_reset='latest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            enable_auto_commit=True
        )

        # keydb for cache connector
        self.keydb_cache_connector = KeyDB(
            host=os.environ.get('KEYDB_HOST', 'localhost'),
            port=os.environ.get('KEYDB_PORT', 6379),
            password=os.environ.get('KEYDB_PASSWORD', None),
            db=os.environ.get('KEYDB_CACHE_DB', 0)
        )

        # keydb for done session
        self.keydb_done_session = KeyDB(
            host=os.environ.get('KEYDB_HOST', 'localhost'),
            port=os.environ.get('KEYDB_PORT', 6379),
            password=os.environ.get('KEYDB_PASSWORD', None),
            db=os.environ.get('KEYDB_DONE_SESSION_DB', 3)
        )

        self.keydb_register_buffer_cache = KeyDB(
            host=os.environ.get('KEYDB_HOST', 'localhost'),
            port=os.environ.get('KEYDB_PORT', 6379),
            password=os.environ.get('KEYDB_PASSWORD', None),
            db=os.environ.get('KEYDB_REGISTER_BUFFER', 6)
        )

        self.face_detector = FaceDetector()
        self.embedder_topic = os.environ.get('KAFKA_EMBEDDER_TOPIC', 'EMBEDDER_QUEUE_')
        self.register_response_topic = os.environ.get('KAFKA_REGISTER_RESPONSE_TOPIC', 'REGISTER_RESPONSE_')
        self.consumer.subscribe(topics=[os.environ.get('KAFKA_DETECTOR_TOPIC', 'DETECTOR_QUEUE_')],
                                listener=ConsumerRebalanceListener())

    def execute(self):
        """
        Listening for message in KAFKA_DETECTOR_QUEUE
        detect face and send to further processing queue.
        :return: None
        """
        self.consumer.poll()
        self.consumer.seek_to_end()
        logger.info('Listening {}..'.format(os.environ.get('KAFKA_DETECTOR_TOPIC', 'DETECTOR_QUEUE_')))

        for message in self.consumer:
            message = message.value

            session = message.get('session', None)
            if session is None:
                logger.warn('Received frame with none session')
                continue

            session_done = self.keydb_done_session.get(session)
            if session_done is None or (session_done is not None and session_done.decode('utf-8') != '-1'):
                logger.warning('Session done. Skipped!')
                continue

            f_type = message.get('f_type', None)
            if f_type is None:
                logger.warn(f'Received frame from session {session} with none f_type')
                continue

            frame_id = message.get('frame_id', None)
            if frame_id is None:
                logger.warn(f'Received frame from session {session} with none frame_id')
                continue

            company_id = message.get('company_id', None)
            if company_id is None:
                logger.warn(f'Received frame from session {session} with none company_id')
                continue

            device = message.get('device', None)
            if device is None:
                logger.warn(f'Received frame from session {session} with none device')
                continue

            logger.info(f'Received message {frame_id} from {session}')
            # generate frame_id
            frame = self.keydb_cache_connector.get(frame_id)
            if frame is None:
                continue

            try:
                # decode base64 string to PIL Image
                frame = Image.open(BytesIO(frame))
                logger.info('Decode success')
            except Exception as ex:
                logger.info('Decode failed')
                logger.exception(ex)
                continue

            frame = cv2.cvtColor(np.array(frame), cv2.COLOR_RGBA2BGR)

            if device == 'ios':
                frame = cv2.flip(frame, 1)

            # cv2.imwrite(os.path.join('static', 'logs', f'{f_type}_{company_id}_{device}_{session}_{frame_id}.png'), frame)

            # detect face from request frame
            detected_result = self.face_detector.detect(frame)
            if detected_result.__len__() <= 0:
                logger.info(f'Skipped - There is no face in {frame_id}')
                continue

            # find the largest face
            landmarks, boxes, max_area = None, None, 0
            for result in detected_result:
                area = result[1][2] * result[1][3]
                if max_area < area:
                    landmarks, boxes, max_area = result[0], result[1], area

            # create FacialLandmark instance and crop face from request frame
            facial_landmark = FacialLandmark(landmarks[0], landmarks[1], landmarks[2], landmarks[3], landmarks[4])
            face = frame[int(boxes[1]): int(boxes[3]), int(boxes[0]): int(boxes[2])]

            cv2.imwrite(os.path.join('static', 'logs', f'{f_type}_{company_id}_{device}_{session}_{frame_id}.png'), face)
            # answer, image = self.face_mask_detector.infer(face)
            # if len(answer) > 0:
            #     if answer[0][0] == 0:
            #         self.keydb_done_session.set(session, 'mask')
            #         logger.info(f'[MASK DETECTED] Received {session}')
            #         continue

            if os.environ.get('DEBUG', None):
                for idx, point in enumerate(landmarks):
                    cv2.circle(frame, (point[0], point[1]), 5, (0, 255, 0), -1)

                cv2.rectangle(frame, (boxes[0],  boxes[1]), (boxes[2], boxes[3]), (255, 0, 0), 2)
                cv2.imwrite(f'static/logs/{frame_id}.png', cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

            # encode cropped face into base64 string
            ret, buffer = cv2.imencode('.jpg', face)
            jpg_as_text = base64.b64encode(buffer)

            # send to embedder queue
            self.producer.send(self.embedder_topic, message)
            self.keydb_cache_connector.set(frame_id,
                                           jpg_as_text,
                                           ex=int(os.environ.get('KEYDB_KEY_TTL', 600)))
            logger.info(f'Sent {frame_id} to {self.embedder_topic}')

            if f_type == 'register':
                employee_id = message.get('employee_id', None)
                if employee_id is None:
                    logger.warn(f'Received frame from session {session} with none id')
                    continue

                # send to register response topic
                self.producer.send(self.register_response_topic, {
                    'session': session,
                    'employee_id': employee_id,
                    'company_id': company_id,
                    'landmarks': facial_landmark.__dict__(),
                    'frame_id': frame_id,
                    'f_type': f_type
                })

                self.keydb_register_buffer_cache.set(session,
                                                     Binary(pickle.dumps(face, protocol=2), subtype=128))

                logger.info(f'Sent {frame_id} to {self.register_response_topic}')

        self.consumer.close()
            

detector_consumer = DetectorConsumer()
detector_consumer.execute()
