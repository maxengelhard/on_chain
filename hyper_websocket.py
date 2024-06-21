import asyncio
import websockets
import json
from loguru import logger
from datetime import datetime, timedelta

class HyperLiquidWebSocket:
    def __init__(self, message_callback) -> None:
        self.message_callback = message_callback
        self.base_uri = "wss://api-ui.hyperliquid.xyz/ws"
        self.websockets = {}
        self.last_message_time = {}

    async def start(self, coins):
        tasks = [self.connect_and_subscribe(coin) for coin in coins]
        await asyncio.gather(*tasks)

    async def connect_and_subscribe(self, coin):
        async with websockets.connect(self.base_uri) as websocket:
            self.websockets[coin] = websocket
            self.last_message_time[coin] = datetime.now()
            await self.subscribe(websocket, coin)
            logger.info(f"HyperLiquid WebSocket connection opened for {coin}.")
            await asyncio.gather(self.handle_update(websocket,coin),self.heartbeat(websocket,coin))

    async def subscribe(self, websocket, coin):
        subscribe_message = {
            "method": "subscribe",
            "subscription": {
                "type": "activeAssetCtx",
                "coin": coin
            }
        }
        await websocket.send(json.dumps(subscribe_message))
        logger.info(f"Sent subscription for {coin}")

    async def handle_update(self, websocket,coin):
        try:
            while True:
                msg = await websocket.recv()
                try:
                    msg = json.loads(msg)
                    self.last_message_time[coin] = datetime.now()
                except:
                    continue
                await self.message_callback(msg)
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"Connection closed: {e}")

    async def heartbeat(self, websocket, coin):
        while True:
            await asyncio.sleep(10)  # Check every 10 seconds
            if datetime.now() - self.last_message_time[coin] >= timedelta(seconds=50):
                ping_message = {"method": "ping"}
                await websocket.send(json.dumps(ping_message))
                logger.info(f"Sent ping to keep connection alive for {coin}")

    async def stop(self):
        for coin, websocket in self.websockets.items():
            await websocket.close()
            logger.info(f"Closed WebSocket connection for {coin}")

async def message_callback(message):
    logger.info(f"Processed message: {message}")

if __name__ == "__main__":
    async def main():
        hyper_websocket = HyperLiquidWebSocket(message_callback=message_callback)
        await hyper_websocket.start(coins=['ETH', 'BTC', 'SOL', 'DOGE'])

    asyncio.run(main())
