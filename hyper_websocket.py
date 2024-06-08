import asyncio
import websockets
import json
from loguru import logger


class HyperLiquidWebSocket:
    def __init__(self, message_callback) -> None:
        self.message_callback = message_callback
        self.base_uri = "wss://api-ui.hyperliquid.xyz/ws"
        self.websocket = None

    async def start(self,coins):
        for coin in coins:
            async with websockets.connect(self.base_uri) as websocket:
                self.websocket = websocket
                await self.subscribe(coin=coin)
                logger.info("AEVO WebSocket connection opened.")
                await self.handle_update()
            

    async def subscribe(self,coin):
        # Subscription message
        subscribe_message = {
            "method": "subscribe",
            "subscription": {
                "type": "activeAssetCtx",
                "coin": coin
            }
        }
        # Send subscription message
        await self.websocket.send(json.dumps(subscribe_message))
        print(f"Sent: {subscribe_message}")


    async def handle_update(self):
        # Continuously listen to messages from the server
        try:
            while True:
                msg = await self.websocket.recv()
                try: msg = json.loads(msg)
                except: continue
                await self.message_callback(msg)
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connection closed: {e}")
    
    async def stop(self):
        if self.websocket:
            await self.websocket.close()
            print("closed hyper websocket")

async def message_callback(message):
    print(f"processed message: {message}")

if __name__ == "__main__":
    async def main():
        hyper_websocket = HyperLiquidWebSocket(message_callback=message_callback)
        await hyper_websocket.start(coin='ETH')

    asyncio.run(main())


