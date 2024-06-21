import asyncio
import os
import traceback
from loguru import logger
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
import aiohttp

from .aevo import AevoLibClient  # Ensure aevo is accessible as a module

class AevoWebSocket:
    def __init__(self, message_callback,coins):
        self.message_callback = message_callback
        self.coins = coins
        self.load_config()
        self.tasks = []
        self.message_queue = asyncio.Queue()
        self.last_message_time = datetime.now()
        self.BASE_URL = "https://api.aevo.xyz"

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

    async def start(self, coins):
        await self.aevo_client.open_connection()
        logger.info("AEVO WebSocket connection opened.")
        self.tasks = [asyncio.create_task(self.subscribe_and_handle_updates(coin)) for coin in coins]
        self.tasks.append(asyncio.create_task(self.read_messages()))
        self.tasks.append(asyncio.create_task(self.heartbeat()))
        self.tasks.append(asyncio.create_task(self.periodic_funding_check()))
        await asyncio.gather(*self.tasks)

    async def subscribe_and_handle_updates(self, coin):
        coin = coin.replace('k', '1000')
        await self.aevo_client.subscribe_tickers(asset=coin, type='PERPETUAL')
        logger.info(f"Subscribed to {coin}")

        while True:
            msg = await self.message_queue.get()
            # logger.debug(f"Processing message for {coin}: {msg}")
            try:
                msg = json.loads(msg)
            except json.JSONDecodeError:
                continue
            await self.message_callback(msg)

    async def read_messages(self):
        try:
            async for msg in self.aevo_client.read_messages():
                await self.message_queue.put(msg)
                self.last_message_time = datetime.now()
        except Exception as e:
            logger.error(f"Error reading messages: {e}")
            logger.error(traceback.format_exc())

    async def heartbeat(self):
        while True:
            await asyncio.sleep(60)  # Check every 10 seconds
            if datetime.now() - self.last_message_time > timedelta(minutes=13):
                ping_message = {"method": "ping"}
                await self.aevo_client.connection.send(json.dumps(ping_message))
                logger.info("Sent ping to keep connection alive")

    async def periodic_funding_check(self):
        while True:
            funding_rates = await self.get_funding(self.coins)
            # Place the funding rates message into the message queue
            msg = json.dumps({'type': 'funding', 'data': funding_rates})
            await self.message_queue.put(msg)

            await asyncio.sleep(300)  # Wait for 5 minutes

    async def get_funding(self,coins:str)-> None:
        result = {}
        async with aiohttp.ClientSession() as session:
            for coin in coins:
                coin_name = coin
                if coin[0] == 'k':
                    coin_name = coin.replace('k', '1000')
                url = f"{self.BASE_URL}/funding?instrument_name={coin_name}-PERP"
                headers = {"accept": "application/json"}
                async with session.get(url, headers=headers) as response:
                    rsp_json = await response.json()
                    result[coin] = float(rsp_json['funding_rate'])
        return result

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        await self.aevo_client.close_connection()
        logger.info("AEVO WebSocket connection closed.")

async def process_aevo_message(msg):
    logger.info(f"Processed message: {msg}")

if __name__ == "__main__":
    async def main():
        manager = AevoWebSocket(message_callback=process_aevo_message)
        await manager.start(coins=['ETH', 'BTC', 'SOL', 'DOGE'])

    asyncio.run(main())
