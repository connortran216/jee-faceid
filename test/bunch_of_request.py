import cv2
import time
import base64
import asyncio
import aiohttp


MAX_REQUESTS = 1000
url = 'http://202.143.110.156:9099/rest/form/'

frame = cv2.imread('static/test.jpg')
r, b = cv2.imencode('.jpg', frame)
jpt = base64.b64encode(b).decode()
f_type = 'recognizer'

message = {
    'f_type': f_type,
    'employee_id': '2363',
    'company_id': '25',
    'device': 'android',
    'is_base64': '1',
    'frame': jpt
}

headers = {
    'token': 'LtPhlLWPgAqyzXHUkf3Vim8UMgtP6hOu',
}


async def req(s_id):
    import uuid
    message['session'] = uuid.uuid4().__str__() + '_' + str(s_id)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url=url, data=message, headers=headers) as response:
                resp = await response.read()
                print(f'Successfully got url {url} with response {resp}.')
    except Exception as ex:
        print(f'Unable to get url {url} due to {ex}')


async def main():
    ret = await asyncio.gather(*[req(i) for i in range(MAX_REQUESTS)])


start = time.time()
import datetime
print(datetime.datetime.now())
asyncio.run(main())
end = time.time()

print("Took {} seconds to send {} requests.".format(end - start, MAX_REQUESTS))
