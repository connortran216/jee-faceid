import os
import json
import uuid
from utils.keydb import KeyDB
from utils.mongo import MongoDatabaseWrapper
from kafka import KafkaProducer
from utils.logger import get_logger
from flask import Flask, request, jsonify
from core.search_client import SearchClient

os.environ['MILVUS_HOST'] = 'milvus'
os.environ['MILVUS_PORT'] = '19530'
os.environ['DB_COLLECTION_NAME'] = 'JFA'


logger = get_logger('REST Service Gateway')
SECRET_KEY = os.environ.get('REST_SECRET_KEY', 'LtPhlLWPgAqyzXHUkf3Vim8UMgtP6hOu')
ERROR_CODE = 1
SUCCESS_CODE = 1
TEMP_DIR = os.path.join('static', 'temp')


class RESTServiceGateway:
    server = Flask('REST Service Gateway')

    keydb_cache_connector = KeyDB(
        host=os.environ.get('KEYDB_HOST', 'localhost'),
        port=os.environ.get('KEYDB_PORT', 6379),
        password=os.environ.get('KEYDB_PASSWORD', None),
        db=os.environ.get('KEYDB_CACHE_DB', 0)
    )

    keydb_done_session = KeyDB(
        host=os.environ.get('KEYDB_HOST', 'localhost'),
        port=os.environ.get('KEYDB_PORT', 6379),
        password=os.environ.get('KEYDB_PASSWORD', None),
        db=os.environ.get('KEYDB_DONE_SESSION_DB', 3)
    )

    # mongo_register_db = MongoDatabaseWrapper('registered_id')
    mongo = MongoDatabaseWrapper()
    search_client = SearchClient()

    kafka_producer = KafkaProducer(bootstrap_servers='192.168.2.160:9092',
                                   value_serializer=lambda v: json.dumps(v).encode('utf-8'))
    topic = os.environ.get('KAFKA_DETECTOR_TOPIC', 'DETECTOR_QUEUE')

    def __init__(self):
        super(RESTServiceGateway, self).__init__()
        logger.info(os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9094'))
        logger.info(RESTServiceGateway.search_client.cursor)

    @staticmethod
    def validate_request(rq):
        if rq.get('session', None) is None:
            return False

        if rq.get('frame', None) is None:
            return False

        f_type = rq.get('f_type', None)
        if f_type not in ['register', 'recognizer']:
            return False

        if f_type == 'register':
            if rq.get('employee_id', None) is None:
                return False

        return True

    @staticmethod
    def response(session, status, data):
        return jsonify(status=status, data={
            'session': session,
            'status': data
        })

    @staticmethod
    @server.route('/rest/form/', methods=['POST'])
    def form():
        try:
            headers = request.headers
            auth = headers.get('token')

            if auth != SECRET_KEY:
                return jsonify(message='ERROR: Authentication error'), 401

            logger.info(request.form)
            session = request.form.get('session', None)
            f_type = request.form.get('f_type', None)
            frame = request.files.get('frame', None)
            employee_id = request.form.get('employee_id', None)
            company_id = request.form.get('company_id', None)

            if company_id is None:
                logger.info(f'Received {session} with none company')
                return RESTServiceGateway.response(session, ERROR_CODE, 'not_existed_company')

            mongo_cursor = RESTServiceGateway.mongo.get_collection('JFA_companies')
            com_id = mongo_cursor.find_one({ '_id': str(company_id)})

            logger.info(f'Received message {session} with f_type: {f_type}')

            if f_type == 'recognizer' and int(employee_id) != -1:
                if com_id is None:
                    logger.info(f'Received {session} with NOT existed company_id: {company_id}')
                    return RESTServiceGateway.response(session, ERROR_CODE, 'not_existed_company')

                if employee_id is None:
                    logger.info(f'Received {session} with none employee_id') 
                    return RESTServiceGateway.response(session, ERROR_CODE, 'not_existed')

                mongo_cursor = RESTServiceGateway.mongo.get_collection(f'{company_id}_registered')
                emp_id = mongo_cursor.find_one({ '_id': str(employee_id)})

                if emp_id is None:
                    logger.info(f'{employee_id} not in database.')
                    return RESTServiceGateway.response(session, ERROR_CODE, 'not_existed')

                if frame is None:
                    logger.info('Skipped first frame')
                    return RESTServiceGateway.response(session, SUCCESS_CODE, 'received')
                # elif os.environ.get('DEBUG', None) is None:
                #     frame.save(os.path.join(TEMP_DIR, secure_filename(frame.filename)))

            if f_type == 'register':
                if employee_id is None:
                    logger.info(f'Received {session} with none employee_id')
                    return RESTServiceGateway.response(session, ERROR_CODE, 'not_existed_employee')

                mongo_cursor = RESTServiceGateway.mongo.get_collection(f'{company_id}_registered')
                registered = mongo_cursor.find_one({ '_id': employee_id })

                if registered is not None \
                        and not RESTServiceGateway.keydb_done_session.get(session):
                    logger.info('Skipped - employee_id exists.')
                    return RESTServiceGateway.response(session, ERROR_CODE, 'existed')

            session_status = RESTServiceGateway.keydb_done_session.get(session)
            if session_status is None:
                RESTServiceGateway.keydb_done_session.set(session, -1)
                logger.info(f'Create new session: {session}')
            elif session_status.decode('utf-8') != '-1':
                if session_status.decode('utf-8') == 'register_done':
                    logger.info(f'Register session done: {session} - Skipped!')
                    return RESTServiceGateway.response(session, SUCCESS_CODE, 'register_done')
                elif session_status.decode('utf-8') == '0' or (employee_id != '-1' and session_status.decode('utf-8') != employee_id):
                    logger.info(f'Recognizer session done - mismatch: {session} - Skipped!')
                    return RESTServiceGateway.response(session, SUCCESS_CODE, 'mismatch_id')
                else:
                    eid = session_status.decode('utf-8')
                    logger.info(f'Recognizer session done with id {eid}: {session} - Skipped!')
                    return jsonify(status=1, data={
                        'status': 'recognizer_done',
                        'recognized_id': session_status.decode('utf-8')
                    })
                    # return RESTServiceGateway.response(session, SUCCESS_CODE, session_status.decode('utf-8'))

            message = {
                'session': session,
                'frame_id': str(uuid.uuid4()),
                'employee_id': request.form.get('employee_id'),
                'f_type': request.form.get('f_type'),
                'company_id': company_id,
                'live': request.form.get('live')
            }

            try:
                RESTServiceGateway.keydb_cache_connector.set(message.get('frame_id'),
                                                             frame.read(),
                                                             ex=os.environ.get('KEYDB_KEY_TTL', 600))
            except Exception as ex:
                logger.info('Can not set frame')

            RESTServiceGateway.kafka_producer.send(RESTServiceGateway.topic, message)
            logger.info(f'Sent a message to {RESTServiceGateway.topic}')

            return RESTServiceGateway.response(session, SUCCESS_CODE, 'received')
        except Exception as ex:
            logger.exception(ex)
            return jsonify(status=ERROR_CODE, data={'data': 'error'})
    
    @staticmethod
    @server.route('/rest/delete/', methods=['GET'])
    def delete():
        #logger.info(f'{RESTServiceGateway.search_client.cursor}')
        try:
            headers = request.headers
            auth = headers.get('token')

            if auth != SECRET_KEY:
                return RESTServiceGateway.response('none_session', ERROR_CODE, 'invalid_token')

            employee_id = request.args.get('employee_id')
            if employee_id is None:
                logger.info('Received NONE employee_id')
                return RESTServiceGateway.response('none_session', ERROR_CODE, 'invalid_employee_id')

            company_id = request.args.get('company_id')
            if company_id is None:
                logger.info('Received NONE company_id')
                return RESTServiceGateway.response('none_session', ERROR_CODE, 'invalid_company_id')
            
            logger.info(f'Received DELETE {employee_id} - {company_id}')

            mongo_cursor = RESTServiceGateway.mongo.get_collection(f'{company_id}_registered')
            mongo_cursor.delete_one({ '_id': employee_id })

            mongo_cursor = RESTServiceGateway.mongo.get_collection(f'{company_id}')
            list_id = mongo_cursor.find({ 'employee_id': employee_id })

            for id in list_id:
                _id = id.get('_id', None)
                if _id is None:
                    continue
                
                RESTServiceGateway.search_client.delete_by_id(f'JFA_Company_{company_id}', _id)

            logger.info(f'Delete {employee_id} from {company_id} success')
            
            return RESTServiceGateway.response('none_session', SUCCESS_CODE, 'success')
        except Exception as ex:
            logger.exception(ex)
            return RESTServiceGateway.response('none_session', ERROR_CODE, 'failed')

    @staticmethod
    @server.route('/rest/get/', methods=['GET'])
    def get():
        headers = request.headers
        auth = headers.get('SECRET_KEY')
        if auth != SECRET_KEY:
            return jsonify(message='ERROR: Authentication error'), 401

        return jsonify(message='OK'), 200

    def start_server(self):
        self.server.run(host=os.environ.get('REST_HOST', '0.0.0.0'),
                        port=os.environ.get('REST_PORT', 5001),
                        debug=True)


rest_service_gateway = RESTServiceGateway().server
# rest_service_gateway.start_server()
# rest_service_gateway = RESTServiceGateway()
# rest_service_gateway.start_server()
