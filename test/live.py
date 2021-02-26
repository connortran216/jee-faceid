import cv2
import uuid
import base64
import requests
from utils.logger import get_logger

logger = get_logger('Live Testing')


video_capture = cv2.VideoCapture(0)
session_id = str(uuid.uuid4())
# url = 'http://115.79.28.221:9077/rest/form/'
# url = 'http://34.87.149.106:9077/rest/form/'
url = 'http://202.143.110.156:9099/rest/form/'

headers = {
    'token': 'LtPhlLWPgAqyzXHUkf3Vim8UMgtP6hOu',
}

while True:
    ret, frame = video_capture.read()

    r, b = cv2.imencode('.jpg', frame)
    jpt = base64.b64encode(b)
    f_type = 'recognizer'
    files = [
        ('frame', jpt)
    ]

    message = {
        'session': session_id,
        'f_type': f_type,
        'employee_id': '-1',
        'company_id': '25',
        'device': 'android',
        'is_base64': '1',
        'frame': jpt
    }

    response = requests.post(url,
                             data=message,
                             headers=headers)
    logger.info(response.json())

    cv2.imshow(f_type, frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
