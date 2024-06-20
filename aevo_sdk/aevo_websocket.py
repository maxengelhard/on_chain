import asyncio
import os
import traceback
from loguru import logger
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta

from .aevo import AevoLibClient  # Ensure aevo is accessible as a module

class AevoWebSocket:
    def __init__(self, message_callback):
        self.message_callback = message_callback
        self.load_config()
        self.tasks = []
        self.message_queue = asyncio.Queue()
        self.last_message_time = datetime.now()

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

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        await self.aevo_client.close_connection()
        logger.info("AEVO WebSocket connection closed.")

    
    async def place_order(self,instrument_id,is_buy,reduce_only,quantity,price):
        logger.info("Creating order...")
        limit_price = 0
        if is_buy:
            limit_price = 2**256 - 1
        # place market order
        response = self.aevo_client.create_order(
            instrument_id=instrument_id,
            is_buy=is_buy,
            quantity=quantity,
            reduce_only=reduce_only,
            limit_price=limit_price
        )
        logger.info(response)

        if not reduce_only:
            parent_order_id = response['order_id']
            # place tp
            take_response = self.place_tp(instrument_id=instrument_id,is_buy=is_buy,quantity=quantity,price=price,parent_order_id=parent_order_id)
            # place sl
            stop_response = self.place_sl(instrument_id=instrument_id,is_buy=is_buy,quantity=quantity,price=price,parent_order_id=parent_order_id)
            return response,take_response,stop_response
        elif reduce_only:
            # TODO cancel tpsl
            return
    
    async def place_tp(self,instrument_id,is_buy,quantity,price,parent_order_id):
        logger.info("Creating tp order...")
        limit_price = 0
        trigger_price = price*(.97) if not is_buy else price*(1.03)
        trigger_price = int(trigger_price * (10**6))
        if not is_buy:
            limit_price = trigger_price * 21
        take_response = self.aevo_client.rest_create_order(
                instrument_id=instrument_id,
                is_buy=not is_buy,
                limit_price=limit_price,
                quantity=0,
                close_position=True,
                reduce_only=True,
                stop='TAKE_PROFIT',
                trigger=trigger_price,
                parent_order_id=parent_order_id
            )
        logger.info(take_response)
        return take_response 


    async def place_sl(self,instrument_id,is_buy,quantity,price,parent_order_id):
        logger.info("Creating sl order...") 
        limit_price = 0
        trigger_price = price*(.97) if is_buy else price*(1.03)
        trigger_price = int(trigger_price * (10**6))
        if is_buy:
            limit_price = trigger_price * 21
        stop_response = self.aevo_client.rest_create_order(
                instrument_id=instrument_id,
                is_buy=not is_buy,
                limit_price=limit_price,
                quantity=0,
                close_position=True,
                reduce_only=True,
                stop='STOP_LOSS',
                trigger=trigger_price,
                parent_order_id=parent_order_id,
            )
        logger.info(stop_response)
        return stop_response

async def process_aevo_message(msg):
    logger.info(f"Processed message: {msg}")

if __name__ == "__main__":
    async def main():
        manager = AevoWebSocket(message_callback=process_aevo_message)
        await manager.start(coins=['ETH', 'BTC', 'SOL', 'DOGE'])

    asyncio.run(main())
