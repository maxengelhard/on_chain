import asyncio
import os
from loguru import logger
import requests
import random
from web3 import AsyncWeb3, Web3
from aiohttp import ClientSession
from eth_abi import encode
import os
from dotenv import load_dotenv

from .aevo import AevoLibClient
from .aevo_trading_tool.aevo_deposit import aevo_deposit


class AevoClient:
    def __init__(self) -> None:
        dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        load_dotenv(dotenv_path=dotenv_path)
        self.ADDRESS = os.environ.get('address')
        self.PRIVATE_KEY = os.environ.get('private_key')
        self.SIGNING_KEY = os.environ.get('signing_key')
        self.API_KEY = os.environ.get('aevo_api')
        self.API_SECRET = os.environ.get('aevo_secret')
        self.BASE_URL = "https://api.aevo.xyz"
        self.COLLATERAL_ADDRESS = "0x643aaB1618c600229785A5E06E4b2d13946F7a1A" # USDC address
        self.WITHDRAW_ADDRESS = "0xE3EF8bEE5c378D4D3DB6FEC96518e49AE2D2b957"  # Withdraw to address
        self.CONNECTOR_ADDRESS = "0x73019b64e31e699fFd27d54E91D686313C14191C"  # socket connector
        self.CHAIN_ID = 42161  # Arbitrum Mainnet chain id
        self.NODE_URL = os.environ.get('rpc_end_point')
        self.TAKER_FEE = 0.0008
        self.MAKER_FEE = 0.0005

        self.aevo_client = AevoLibClient(
            signing_key=self.SIGNING_KEY,
            wallet_address=self.ADDRESS,
            api_key=self.API_KEY,
            api_secret=self.API_SECRET,
            env="mainnet",
        )

    def update_leverage(self,leverage,coin):
        market_data = self.get_markets(asset=coin,instrument='PERPETUAL')
        instrument_id = market_data[0]['instrument_id']
        update_leverage_rsp = self.aevo_client.update_leverage(instrument_id=instrument_id,leverage=leverage)
        logger.info(f'Updated leverage on AEVO for {coin}: {leverage}')
        return update_leverage_rsp


    def place_order(self,instrument_id,is_buy,reduce_only,quantity,limit_px):
        if not reduce_only: logger.info(f"Creating aevo {'Buy' if is_buy else 'Sell'} order for {instrument_id}")
        else: logger.info(f"Closing aevo order for {instrument_id}")
        
        try:
            # place market order
            # response = self.aevo_client.rest_create_market_order(
            #     instrument_id=instrument_id,
            #     is_buy=is_buy,
            #     quantity=quantity,
            #     reduce_only=reduce_only,
            # )
            # place limit order
            response = self.aevo_client.rest_create_order( 
                instrument_id=instrument_id,
                is_buy=is_buy,
                quantity=quantity,
                reduce_only=reduce_only, 
                limit_price=limit_px
            )
            logger.info(response)
            return response
        except Exception as e:
            if not reduce_only: logger.info(f"Error creating aevo order. Error: {e}")
            else: logger.info(f"Error closing aevo order. Error: {e}")



    def place_tpsl(self,instrument_id,is_buy,quantity,high_price,low_price):
        take_price = high_price if is_buy else low_price
        stop_price = low_price if is_buy else high_price
        # place tp
        take_response = self.place_tp(instrument_id=instrument_id,is_buy=is_buy,quantity=quantity,price=take_price)
        # place sl
        stop_response = self.place_sl(instrument_id=instrument_id,is_buy=is_buy,quantity=quantity,price=stop_price)

        return take_response, stop_response

    
    def place_tp(self,instrument_id,is_buy,price):
        logger.info("Creating tp order...")
        limit_price = 0
        trigger_price = int(price * (10**6))
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
                post_only=False,
                time_in_force='IOC',
            )
        logger.info(take_response)
        return take_response 


    def place_sl(self,instrument_id,is_buy,price):
        logger.info("Creating sl order...") 
        limit_price = 0
        trigger_price = int(price * (10**6))
        if not is_buy:
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
                post_only=False,
                time_in_force='IOC',
            )
        logger.info(stop_response)
        return stop_response


    async def get_account(self) -> None:
        logger.info("Getting AEVO portfolio...")
        response = self.aevo_client.rest_get_account()
        return response

    async def get_fundings(self) -> None:
        response = self.aevo_client.rest_get_account_fundings()
        return response


    async def get_positions(self) -> None:
        response = self.aevo_client.rest_get_positions()
        return response


    def get_markets(self,asset,instrument) -> None:
        response = self.aevo_client.get_markets(asset,instrument)
        return response


    def get_funding(self,coins:str)-> None:
        result = {}
        for coin in coins:
            coin_name = coin
            if coin[0] == 'k':
                coin_name = coin.replace('k','1000')
            url = f"{self.BASE_URL}/funding?instrument_name={coin_name}-PERP"
            headers = {"accept": "application/json"}
            response = requests.get(url, headers=headers)
            rsp_json = response.json()
            result[coin] = rsp_json['funding_rate']
        
        return result
    
    async def deposit(self,amount:float)-> None:
        await aevo_deposit(amount=amount)

    async def sign_withdraw(
            self,
            web3: AsyncWeb3,
            collateral: str,
            to: str,
            amount: int,
            salt: int,
            private_key: str,
            socket_fees: int,
            socket_msg_gas_limit: int,
            socket_connector: str
    ) -> str:
        data = encode(
            ["uint256", "uint256", "address"],
            [socket_fees, socket_msg_gas_limit, socket_connector]
        )

        key_signature = web3.eth.account.sign_typed_data(
            domain_data={
                "name": "Aevo Mainnet",
                "version": "1",
                "chainId": self.CHAIN_ID,
            },
            message_types={
                "Withdraw": [
                    {"name": "collateral", "type": "address"},
                    {"name": "to", "type": "address"},
                    {"name": "amount", "type": "uint256"},
                    {"name": "salt", "type": "uint256"},
                    {"name": "data", "type": "bytes32"}
                ]
            },
            message_data={
                "collateral": web3.to_checksum_address(collateral),
                "to": web3.to_checksum_address(to),
                "amount": amount,
                "salt": salt,
                "data": web3.keccak(data)
            },
            private_key=private_key
        )
        return key_signature.signature.hex()

    async def withdraw(self, amount: float):
        web3 = AsyncWeb3(Web3.HTTPProvider(self.NODE_URL))
        salt = random.randint(0, 10 ** 10)
        amount_in_micro = int(amount * 10 ** 6)  # Convert amount to micro-units as expected by the contract
        socket_fees = random.randint(4326304606198636, 4326309606198636)
        socket_msg_gas_limit = 2000000

        signature = await self.sign_withdraw(
            web3, self.COLLATERAL_ADDRESS, self.WITHDRAW_ADDRESS, amount_in_micro, salt, self.PRIVATE_KEY,
            socket_fees, socket_msg_gas_limit, self.CONNECTOR_ADDRESS
        )

        payload = {
            "account": web3.to_checksum_address(self.ADDRESS),
            "amount": str(amount_in_micro),
            "collateral": web3.to_checksum_address(self.COLLATERAL_ADDRESS),
            "salt": str(salt),
            "signature": signature,
            "socket_connector": self.CONNECTOR_ADDRESS,
            "socket_fees": str(socket_fees),
            "socket_msg_gas_limit": str(socket_msg_gas_limit),
            "to": web3.to_checksum_address(self.WITHDRAW_ADDRESS),
        }

        async with ClientSession() as session:
            response = await session.post(f'{self.BASE_URL}/withdraw', json=payload)
            response_data = await response.json()
            if response.status != 200:
                logger.error(f"Something went wrong: {response_data}")
                return

            logger.info(f"Successfully withdrawn {amount} USDC")


if __name__ == "__main__":
    # asyncio.run(aevo_create_order(instrument_id=1,is_buy=False,reduce_only=True,quantity=0.01))
    # response = asyncio.run(aevo_markets(asset='ETH',instrument='PERPETUAL'))
    aevo_client = AevoClient()
    instrument_id = 1
    size = 0.01

    response = asyncio.run(aevo_client.place_order(instrument_id=instrument_id,is_buy=True,reduce_only=False,quantity=size))
    print(response)

