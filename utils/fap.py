import json
import requests


url = 'http://valapi:5002/fap_binary/'


def send_fap_request(session, b) -> int:
    try:
        payload = {
            'session_id': session
        }
        files = [
            ('image_bin', b)
        ]
        headers = {}
        response = requests.post(url, headers=headers, data=json.dumps(payload), files=files)
    except Exception as ex:
        print('ERROR:', ex)
        return 0

    print(response.json()['message'])
    return int(response.json()['message'])
