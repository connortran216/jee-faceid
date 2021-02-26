import os
import json
import asyncio
import websockets
from utils.logger import get_logger
from kafka import KafkaProducer
from websockets import WebSocketServerProtocol

logger = get_logger('WebSocket Service Gateway')


class WebSocketServiceGateway:
    clients = set()
    kafka_producer = KafkaProducer(bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9094'),
                                   value_serializer=lambda v: json.dumps(v).encode('utf-8'))
    topic = os.environ.get('KAFKA_DETECTOR_TOPIC', 'DETECTOR_QUEUE')

    async def register(self, ws: WebSocketServerProtocol) -> None:
        self.clients.add(ws)
        logger.info(f'{ws.remote_address} connects.')

    async def unregister(self, ws: WebSocketServerProtocol) -> None:
        self.clients.remove(ws)
        logger.info(f'{ws.remote_address} disconnects.')

    async def send_to_clients(self, message) -> None:
        if self.clients:
            await asyncio.wait([client.send(message) for client in self.clients])

    async def ws_handler(self, ws: WebSocketServerProtocol, uri: str) -> None:
        await self.register(ws)
        try:
            await self.distribute(ws)
        finally:
            await self.unregister(ws)

    async def distribute(self, ws: WebSocketServerProtocol) -> None:
        async for message in ws:
            self.kafka_producer.send(self.topic, message)
            logger.info(f'Sent message from {ws.remote_address} to {self.topic}')


server = WebSocketServiceGateway()
logger.info('Listening..')
start_server = websockets.serve(server.ws_handler,
                                os.environ.get('WEBSOCKET_HOST', 'localhost'),
                                os.environ.get('WEBSOCKET_PORT', 4000))
loop = asyncio.get_event_loop()
loop.run_until_complete(start_server)
loop.run_forever()
