import json
import asyncio
import websockets


async def produce(host: str, port: int) -> None:
    async with websockets.connect(f'ws://{host}:{port}') as ws:
        for message in range(100000):
            await ws.send(message.__str__())
            await ws.recv()
            print(f'Sent {message}')


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(produce(host='localhost', port=4000))
