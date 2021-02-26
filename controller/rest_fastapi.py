import os
import json
import uuid
import base64
from typing import Optional
from fastapi import FastAPI
from utils.keydb import KeyDB
from bson.objectid import ObjectId
from utils.logger import get_logger
from core.search_client import SearchClient
from utils.mongo import MongoDatabaseWrapper
from kafka import KafkaProducer
from fastapi import File, Form, Header
from pydantic import BaseModel
from utils.fap import send_fap_request
from fastapi.openapi.utils import get_openapi


logger = get_logger('JFA REST Server Gateway')
SECRET_KEY = os.environ.get('REST_SECRET_KEY', 'LtPhlLWPgAqyzXHUkf3Vim8UMgtP6hOu')


class ResponseCode:
    ERROR_CODE = 0
    SUCCESS_CODE = 1


class FAPCode:
    ENABLE = True
    RECEIVED = 0
    CHEAT = 1
    MASK = 2
    MIX = 3
    ACCEPTED = 4


class SessionResponseBody(BaseModel):
    session: str
    status: str
    recognized_id: Optional[str]


class ResponseModel(BaseModel):
    status: str
    data: SessionResponseBody

    class Config:
        schema_extra = {
            'example': [
                {
                    'status': ResponseCode.SUCCESS_CODE,
                    'data': {
                        'session': str(uuid.uuid4()),
                        'status': 'recognizer_done',
                        'recognized_id': None
                    }
                },
                {
                    'status': ResponseCode.SUCCESS_CODE,
                    'data': {
                        'session': str(uuid.uuid4()),
                        'status': 'register_done',
                        'recognized_id': '2311'
                    }
                },
                {
                    'status': ResponseCode.SUCCESS_CODE,
                    'data': {
                        'session': str(uuid.uuid4()),
                        'status': 'register_done',
                        'recognized_id': None
                    }
                },
                {
                    'status': ResponseCode.SUCCESS_CODE,
                    'data': {
                        'session': str(uuid.uuid4()),
                        'status': 'mismatch_id',
                        'recognized_id': None
                    }
                },
                {
                    'status': ResponseCode.SUCCESS_CODE,
                    'data': {
                        'session': str(uuid.uuid4()),
                        'status': 'mask_detected',
                        'recognized_id': None
                    }
                },
                {
                    'status': ResponseCode.SUCCESS_CODE,
                    'data': {
                        'session': str(uuid.uuid4()),
                        'status': 'cheat_detected',
                        'recognized_id': None
                    }
                },
                {
                    'status': ResponseCode.SUCCESS_CODE,
                    'data': {
                        'session': str(uuid.uuid4()),
                        'status': 'not_existed',
                        'recognized_id': None
                    }
                },
                {
                    'status': ResponseCode.SUCCESS_CODE,
                    'data': {
                        'session': str(uuid.uuid4()),
                        'status': 'not_existed_company',
                        'recognized_id': None
                    }
                },
                {
                    'status': ResponseCode.ERROR_CODE,
                    'data': {
                        'session': str(uuid.uuid4()),
                        'status': 'invalid_token',
                        'recognized_id': None
                    }
                },
                {
                    'status': ResponseCode.SUCCESS_CODE,
                    'data': {
                        'session': str(uuid.uuid4()),
                        'status': 'received',
                        'recognized_id': None
                    }
                },
                {
                    'status': ResponseCode.ERROR_CODE,
                    'data': {
                        'session': str(uuid.uuid4()),
                        'status': 'internal_server_error',
                        'recognized_id': None
                    }
                },
                {
                    'status': ResponseCode.ERROR_CODE,
                    'data': {
                        'session': str(uuid.uuid4()),
                        'status': 'failed',
                        'recognized_id': None
                    }
                }
            ]
        }


class RestServiceGateway:
    server = FastAPI(
        title='JeeHR Face Attendance',
        description='Face recognition system that empower human resources management.',
        version='1.0.0'
    )

    tags_metadata = [
        {
            'name': 'CRUD',
            'description': 'Basic system interactive operations.'
        }
    ]

    response_models = {
        'foo': {
            'status': 'Work status',
            'data': {
                'session': 'Uploaded session',
                'status': 'Session status'
            }
        }
    }

    keydb_cache_connector = KeyDB(
        host=os.environ.get('KEYDB_HOST', 'localhost'),
        port=os.environ.get('KEYDB_PORT', 6379),
        password=os.environ.get('KEYDB_PASSWORD', None),
        db=os.environ.get('KEYDB_CACHE_DB', 0)
    )

    keydb_done_session_connector = KeyDB(
        host=os.environ.get('KEYDB_HOST', 'localhost'),
        port=os.environ.get('KEYDB_PORT', 6379),
        password=os.environ.get('KEYDB_PASSWORD', None),
        db=os.environ.get('KEYDB_DONE_SESSION_DB', 3)
    )

    search_client = SearchClient()
    mongo = MongoDatabaseWrapper()

    kafka_producer = KafkaProducer(bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9094'),
                                   value_serializer=lambda v: json.dumps(v).encode('utf-8'))

    topic = os.environ.get('KAFKA_DETECTOR_TOPIC', 'DETECTOR_QUEUE')

    def __init__(self):
        super(RestServiceGateway, self).__init__()
        logger.info('Initialized REST Service Gateway')
        logger.info(RestServiceGateway.kafka_producer)

    @staticmethod
    def create_response(status, session, session_st):
        return ResponseModel(status=status, data=SessionResponseBody(session=session, status=session_st))

    @staticmethod
    @server.post('/rest/form/',
                 tags=['CRUD'],
                 response_model=ResponseModel)
    async def form(token: str = Header(...,
                                       title='Authentication token',
                                       description='Authentication token which was provided by DPS Admin.'),
                   frame: Optional[str] = Form(...,
                                               title='Frame content',
                                               description='Image content that can be binary or base64.'),
                   session: str = Form(...,
                                       title='Session identifier',
                                       description='An unique string that can be use to distinguish with other session.'
                                       ),
                   employee_id: str = Form(...,
                                           title='Employee identifier',
                                           description='An unique string of a specific employee that can be use to '
                                                       'distinguish with other employee identifier. This field also '
                                                       'might be \"-1\" if you want to use recognizer module.'),
                   f_type: str = Form(...,
                                      title='Request type',
                                      description='Request type: register, register_image, recognizer.'),
                   company_id: str = Form(...,
                                          title='Company identifier',
                                          description='An unique string of a specific company that can be use to '
                                                      'distinguish with other company identifier.'),
                   device: str = Form(...,
                                      title='Device type',
                                      description='Source device type: android, ios.'),
                   is_base64: Optional[str] = Form(...,
                                                   title='Frame type',
                                                   description='Frame data type: base64 data if is_base64 = 1 else raw '
                                                               'binary.')):
        logger.info(f'Started to process {session}')

        try:
            # check static token
            if token != SECRET_KEY:
                return RestServiceGateway.create_response(ResponseCode.ERROR_CODE, session, 'invalid_token')

            # find company record by company ID
            mongo_companies = RestServiceGateway.mongo.get_collection('JFA_Companies')
            comp_id = mongo_companies.find_one({
                '_id': str(company_id)
            })

            # check if this session is on-register status
            if RestServiceGateway.keydb_cache_connector.get(f'{session}_register_status') == 'on-register':
                return RestServiceGateway.create_response(session, ResponseCode.SUCCESS_CODE, 'on-register')

            if f_type == 'register_image':
                logger.info(f'Received {session}: register image')
                mongo_employees = RestServiceGateway.mongo.get_collection(f'{company_id}_registered')
                registered = mongo_employees.find_one({
                    '_id': employee_id
                })
                
                logger.info(registered)
                if registered is not None:
                    logger.info(f'[SKIPPED] employee_id {employee_id} existed.')
                    return RestServiceGateway.create_response(session, ResponseCode.SUCCESS_CODE, 'existed')

                RestServiceGateway.keydb_cache_connector.set(f'{session}_register_status',
                                                             'on-register',
                                                             ex=os.environ.get('KEYDB_KEY_TTL, 600'))

            if f_type == 'recognizer' and int(employee_id) == -1:
                if comp_id is None:
                    logger.info(f'Received {session} with NOT existed company_id: {company_id}')
                    return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'not_existed_company')

                if is_base64 == '1':
                    if len(frame) < 10:
                        logger.info(f'[SKIPPED] Skipped first frame of session {session}')
                        return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'received')

            if f_type == 'recognizer' and int(employee_id) != -1:
                mongo_employees = RestServiceGateway.mongo.get_collection(f'{company_id}_registered')
                emp_id = mongo_employees.find_one({
                    '_id': str(employee_id)
                })

                if emp_id is None:
                    logger.info(f'{employee_id} not in database')
                    return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'not_existed')

                if is_base64 == '1':
                    if len(frame) < 10:
                        logger.info(f'[SKIPPED] Skipped first frame of session {session}')
                        return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'received')

                f_type = 'verifier'

            elif f_type == 'register' or f_type == 'register_image':
                mongo_employees = RestServiceGateway.mongo.get_collection(f'{company_id}_registered')
                registered = mongo_employees.find_one({
                    '_id': employee_id
                })
                
                if registered is not None and not RestServiceGateway.keydb_done_session_connector.get(session):
                    logger.info('Skipped - employee_id exists.')
                    return RestServiceGateway.create_response(session, ResponseCode.SUCCESS_CODE, 'existed')

            logger.info(f'Received request [{session} - {company_id} - {employee_id} - {f_type} - {device} '
                        f'- {is_base64}]')

            session_status = RestServiceGateway.keydb_done_session_connector.get(session)
            if session_status is None:
                RestServiceGateway.keydb_done_session_connector.set(session, -1, ex=os.environ.get('KEYDB_KEY_TTL',
                                                                                                   600))
                logger.info(f'Create new session: {session}')
            else:
                session_status = session_status.decode('utf-8')

                if FAPCode.ENABLE is True:
                    if session_status == 'cheated':
                        logger.info(f'[SKIPPED] Cheating detected from company id: {company_id} - employee id: '
                                    f'{employee_id}.')
                        return RestServiceGateway.create_response(session, ResponseCode.SUCCESS_CODE, 'cheat_detected')
                    elif session_status == 'mask':
                        logger.info(f'[SKIPPED] Mask detected from company id: {company_id} '
                                    f'- employee id: {employee_id}.')
                        return RestServiceGateway.create_response(session, ResponseCode.SUCCESS_CODE, 'mask_detected')

                if session_status != '-1':
                    if session_status == 'register_done':
                        logger.info(f'[Skipped] Register employee {employee_id} of company {company_id} with session '
                                    f'{session} done.')
                        return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'register_done')
                    elif session_status == 'mask':
                        logger.info(f'[Skipped] Mask detected {employee_id} of company {company_id} with session '
                                    f'{session}.')
                        return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'mask_detected')
                    elif session_status == '0' or (employee_id != '-1' and session_status != employee_id):
                        logger.info(f'[Skipped] Recognizer session done - mismatch [{session_status} - {employee_id}]: '
                                    f'{session}')
                        return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'mismatch_id')
                    else:
                        logger.info(f'[Skipped] Recognizer done with id {session_status} in session {session}')
                        return {
                            'status': ResponseCode.SUCCESS_CODE,
                            'data': {
                                'session': session,
                                'status': 'recognizer_done',
                                'recognized_id': session_status
                            }
                        }

            message = {
                'session': session,
                'frame_id': str(uuid.uuid4()),
                'employee_id': employee_id,
                'company_id': company_id,
                'f_type': f_type,
                'device': device
            }

            try:
                if is_base64 == '1':
                    frame = base64.b64decode(frame)
            except Exception as ex:
                logger.info(f'Can not decode.')
                logger.exception(ex)
                logger.info(frame)
                return RestServiceGateway.create_response(ResponseCode.ERROR_CODE, session, 'internal_server_error')

            if FAPCode.ENABLE is True:
                if f_type in ['recognizer', 'verifier']:
                    catch_bitch = send_fap_request(session, frame)
                    if catch_bitch == FAPCode.CHEAT:    # cheated case
                        RestServiceGateway.keydb_done_session_connector.set(session, 'cheated')
                        logger.info('[SKIPPED] Cheating detected.')
                        return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'cheat_detected')
                    elif catch_bitch == FAPCode.MASK:   # mask case
                        RestServiceGateway.keydb_done_session_connector.set(session, 'mask')
                        logger.info('[SKIPPED] Mask detected.')
                        return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'mask_detected')
                    elif catch_bitch == FAPCode.MIX:    # cheat and mask case
                        RestServiceGateway.keydb_done_session_connector.set(session, 'cheated')
                        logger.info('[SKIPPED] Cheat and mask detected')
                        return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'cheat_detected')
                    else:
                        logger.info('Accepted frame.')

            try:
                RestServiceGateway.keydb_cache_connector.set(message.get('frame_id'),
                                                             frame,
                                                             ex=os.environ.get('KEYDB_KEY_TTL', 600))
            except Exception as ex:
                logger.info(f'[Skipped] Session {session} failed: can not set frame.')
                logger.exception(ex)
                return RestServiceGateway.create_response(ResponseCode.ERROR_CODE, session, 'internal_server_error')

            RestServiceGateway.kafka_producer.send(RestServiceGateway.topic, message)
            logger.info(f'Sent a message to {RestServiceGateway.topic}')

            if f_type == 'register_image':
                return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'register_done')
            else:
                return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'received')
        except Exception as ex:
            logger.exception(ex)
            return RestServiceGateway.create_response(ResponseCode.ERROR_CODE, session, 'internal_server_error')
    
    @staticmethod
    @server.get('/rest/get/', tags=['CRUD'])
    async def get_image(employee_id: str,
                        company_id: str,
                        token: str = Header(...)):
        session = 'none_session'
        try:
            if token != SECRET_KEY:
                return RestServiceGateway.create_response(ResponseCode.ERROR_CODE, session, 'invalid_token')
            
            logger.info(f'[GET_IMAGE] employee_id: {employee_id} - company_id: {company_id}')
            mongo = RestServiceGateway.mongo.get_collection(f'JFA_Company_{company_id}_register_buffer_pool')
            records = mongo.find({
                'employee_id': employee_id,
                'company_id': company_id
            })

            res = list()
            for item in records:
                item['_id'] = str(item['_id'])
                item['feature'] = None
                res.append(item)

            return {
                'status': '1',
                'data': {
                    'session': session,
                    'status': 'get_done',
                    'num_frames': len(res),
                    'frames': res
                }
            }

        except Exception as ex:
            logger.exception(ex)
            return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'failed')

    @staticmethod
    @server.get('/rest/delete/', tags=['CRUD'])
    async def delete(employee_id: str,
                     company_id: str,
                     token: str = Header(...)):

        session = 'none_session'
        try:
            if token != SECRET_KEY:
                return RestServiceGateway.create_response(ResponseCode.ERROR_CODE, session, 'invalid_token')

            logger.info(f'[DELETE] employee_id: '
                        f'{employee_id} - company_id: {company_id}')

            mongo_company = RestServiceGateway.mongo.get_collection(f'JFA_Companies')
            check = mongo_company.find_one({
                '_id': company_id
            })

            if check is None:
                return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'not_existed_company')

            mongo_employees = RestServiceGateway.mongo.get_collection(f'{company_id}_registered')
            check = mongo_employees.find_one({
                '_id': employee_id
            })

            if check is None:
                return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'not_existed')

            mongo_employees.delete_one({
                '_id': employee_id
            })

            mongo_pos = RestServiceGateway.mongo.get_collection(f'{company_id}')
            list_id = mongo_pos.find({
                'employee_id': employee_id
            })

            for id in list_id:
                _id = id.get('_id', None)
                if _id is None:
                    continue
                
                mongo_pos.delete_one({
                    '_id': _id
                })

                RestServiceGateway.search_client.delete_by_id(f'JFA_Company_{company_id}', _id)

            mongo_pool = RestServiceGateway.mongo.get_collection(f'JFA_Company_{company_id}_register_buffer_pool')
            mongo_pool.delete_many({
                'company_id': company_id,
                'employee_id': employee_id
            })

            logger.info(f'[DELETE] Delete {employee_id} from {company_id} success')
            return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'success')
        except Exception as ex:
            logger.exception(ex)
            return RestServiceGateway.create_response(ResponseCode.ERROR_CODE, session, 'failed')

    @staticmethod
    @server.get('/rest/delete_frame/', tags=['CRUD'])
    async def delete_frame(employee_id: str,
                           company_id: str,
                           frame_id: str,
                           token: str = Header(...)):
        session = 'none_session'

        try:
            if token != SECRET_KEY:
                return RestServiceGateway.create_response(ResponseCode.ERROR_CODE, session, 'invalid_token')

            frame_id = ObjectId(frame_id)

            logger.info(f'[DELETE FRAME] employee_id: '
                        f'{employee_id} - company_id: {company_id} - '
                        f'frame_id: {frame_id}')

            mongo_company = RestServiceGateway.mongo.get_collection(f'JFA_Companies')
            check = mongo_company.find_one({
                '_id': company_id
            })

            if check is None:
                return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'not_existed_company')

            mongo_employees = RestServiceGateway.mongo.get_collection(f'{company_id}_registered')
            check = mongo_employees.find_one({
                '_id': employee_id
            })

            if check is None:
                return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'not_existed')

            mongo_pool = RestServiceGateway.mongo.get_collection(f'JFA_Company_{company_id}_register_buffer_pool')
            check = mongo_pool.find_one({
                '_id': frame_id,
                'employee_id': employee_id,
                'company_id': company_id
            })

            if check is None:
                return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'not_existed_frame')

            # delete in milvus
            position = check['pos']
            RestServiceGateway.search_client.delete_by_id(f'JFA_Company_{company_id}', position)

            # delete in register pool
            mongo_pool.delete_one({
                '_id': frame_id,
                'employee_id': employee_id,
                'company_id': company_id
            })

            # delete in position id
            mongo_pos = RestServiceGateway.mongo.get_collection(f'{company_id}')
            mongo_pos.delete_one({
                '_id': position,
                'employee_id': employee_id
            })

            # if this is the last one, delete registered status of employee
            if mongo_pos.find_one({ 'employee_id': employee_id }) is None:
                # delete in registered
                registered = RestServiceGateway.mongo.get_collection(f'{company_id}_registered')
                registered.delete_one({
                    '_id': employee_id
                })

            return RestServiceGateway.create_response(ResponseCode.SUCCESS_CODE, session, 'success')
        except Exception as ex:
            logger.exception(ex)
            return RestServiceGateway.create_response(ResponseCode.ERROR_CODE, session, 'failed')


server = RestServiceGateway()
server = server.server


def custom_openapi():
    if server.openapi_schema:
        return server.openapi_schema
    openapi_schema = get_openapi(
        title="JeeHR Face Attendance",
        version="1.0.0",
        description="Face Recognition System That Empower Human Resources Management.",
        routes=server.routes,
    )
    server.openapi_schema = openapi_schema
    return server.openapi_schema


server.openapi = custom_openapi
