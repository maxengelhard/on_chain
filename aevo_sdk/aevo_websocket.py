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
        self.message_queue = asyncio.Queue() # queue to store messages
        self.last_message_time = datetime.now()
        self.BASE_URL = "https://api.aevo.xyz"
        self.order_event = asyncio.Event()  # Event to trigger order placement
        self.order_queue = asyncio.Queue() # Queue to store orders
        self.connected_event = asyncio.Event()  # Event to signal that WebSocket is connected

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
        self.connected_event.set() 
        coins.append('pos')
        self.tasks = [
            asyncio.create_task(self.subscribe_and_handle_updates(coin)) for coin in self.coins
        ]
        self.tasks.extend([
            asyncio.create_task(self.read_messages()),
            asyncio.create_task(self.heartbeat()),
            asyncio.create_task(self.periodic_funding_check()),
            # asyncio.create_task(self.handle_order_event())
        ])
        await asyncio.gather(*self.tasks)

    async def subscribe_and_handle_updates(self, coin):
        if coin == 'pos':
            await self.aevo_client.subscribe_postitions()
            logger.info("subscribed to postitions")
        else:
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
                # logger.debug(f"Received message: {msg}")
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
            # logger.info("Added funding rates to message queue")

            await asyncio.sleep(300)  # Wait for 5 minutes

    async def get_funding(self,coins:str)-> None:
        result = {}
        async with aiohttp.ClientSession() as session:
            for coin in coins:
                if coin == 'pos': continue
                coin_name = coin
                if coin[0] == 'k':
                    coin_name = coin.replace('k', '1000')
                url = f"{self.BASE_URL}/funding?instrument_name={coin_name}-PERP"
                headers = {"accept": "application/json"}
                async with session.get(url, headers=headers) as response:
                    rsp_json = await response.json()
                    result[coin] = float(rsp_json['funding_rate'])
        return result


    async def handle_order_event(self):
        while True:
            logger.info("waiting for order event.. ")
            await self.order_event.wait()
            logger.info("Order event set")
            order_params = await self.order_queue.get() # get order params from queue
            logger.info(f"Order event triggered with params: {order_params}")
            await self.place_order(*order_params)
            self.order_event.clear()

    # place order
    async def place_order(self,instrument_id,is_buy,reduce_only,quantity):
        logger.info("Creating ws order...")
        limit_price = 0
        if is_buy:
            limit_price = 1000000
        # place market order
        response = await self.aevo_client.create_order(
            instrument_id=instrument_id,
            is_buy=is_buy,
            quantity=quantity,
            limit_price=limit_price
            # reduce_only=reduce_only,
        )
        logger.info(response)

        return response
    
    async def cancel_order(self,order_id):
        order_id = await self.aevo_client.cancel_order(
        order_id=order_id,
    )

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        await self.aevo_client.close_connection()
        logger.info("AEVO WebSocket connection closed.")

async def process_aevo_message(msg):
    # return
    logger.info(f"Processed message: {msg}")

if __name__ == "__main__":
    async def main():
        manager = AevoWebSocket(message_callback=process_aevo_message,coins=['ETH', 'BTC', 'SOL', 'DOGE'])
        # Start the websocket as a background task
        ws_task = asyncio.create_task(manager.start(coins=['ETH', 'BTC', 'SOL', 'DOGE']))

        await manager.connected_event.wait()
        logger.info("WebSocket connection established.")

        logger.info("Putting order into queue and setting event.")
        await manager.order_queue.put((1,True,False,0.01))
        manager.order_event.set()
        # await manager.place_order(instrument_id=1,is_buy=True,reduce_only=False,quantity=0.01)
        # await asyncio.sleep(1)


    asyncio.run(main())
