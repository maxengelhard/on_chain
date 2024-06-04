# aevo_websocket_manager.py

import asyncio
import os
from loguru import logger
from dotenv import load_dotenv
import json

from .aevo import AevoLibClient  # Ensure aevo is accessible as a module

class AevoWebSocket:
    def __init__(self,message_callback):
        self.message_callback = message_callback
        self.load_config()

    def load_config(self):
        dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        load_dotenv(dotenv_path=dotenv_path)
        self.address = os.environ.get('address')
        self.private_key = os.environ.get('private_key')
        self.signing_key = os.environ.get('signing_key')
        self.api_key = os.environ.get('aevo_api')
        self.api_secret = os.environ.get('aevo_secret')
        self.aevo_client = AevoLibClient(
            signing_key=self.signing_key,
            wallet_address=self.address,
            api_key=self.api_key,
            api_secret=self.api_secret,
            env="mainnet",
        )

    async def start(self,coin):
        await self.aevo_client.open_connection()
        logger.info("AEVO WebSocket connection opened.")
        await self.handle_update(coin=coin)

    async def handle_update(self,coin):
        logger.info("Creating subscription for mark price...")
        # await self.aevo_client.subscribe_markprice(asset=coin, type='PERPETUAL')
        await self.aevo_client.subscribe_tickers(asset=coin,type='PERPETUAL')

        async for msg in self.aevo_client.read_messages():
            # logger.info(f"Received message: {msg}")
            try: msg=json.loads(msg)
            except: continue
            await self.message_callback(msg)

    async def stop(self):
        if self.aevo_client:
            await self.aevo_client.close_connection()
            logger.info("AEVO WebSocket connection closed.")

async def process_aevo_meesage(msg):
    print(msg)

# If the module is executed directly, perform a sample connection and subscription
if __name__ == "__main__":
    async def main():
        manager = AevoWebSocket(message_callback=process_aevo_meesage)
        await manager.start(coin='ETH')

    asyncio.run(main())
