import time
import requests
import json
from eth_account import Account
from eth_account.signers.local import LocalAccount
import json
import os
from web3 import Web3
from web3.middleware import geth_poa_middleware

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

from trading_utils import round_price

from dotenv import load_dotenv

class HyperLiquidClient:
    def __init__(self):
        load_dotenv()
        self.ADDRESS = os.environ.get('address')
        self.SECRET_KEY = os.environ.get('private_key')
        self.BASE_URL = constants.MAINNET_API_URL
        self.ACCOUNT = Account.from_key(self.SECRET_KEY)
        self.USDC_CONTRACT_ADDRESS = Web3.to_checksum_address(os.environ.get('usdc_contract'))
        self.USDCE_CONTRACT_ADDRESS = Web3.to_checksum_address(os.environ.get('usdce_contract'))
        self.NODE_URL = os.environ.get('rpc_end_point')
        self.HYPER_ADDRESS = Web3.to_checksum_address(os.environ.get('hyper_liquid_address'))
        self.TAKER_FEE = 0.00035
        self.MAKER_FEE = 0.0001
        
        self.info = Info(self.BASE_URL, skip_ws=True)
        self.exchange = Exchange(self.ACCOUNT, self.BASE_URL, account_address=self.ADDRESS)
        
    def get_account(self) -> None:
        user_info = self.info.user_state(address=self.ADDRESS)
        return user_info

    def get_funding(self,coins:list) -> None:
        url = f"{self.BASE_URL}/info"
        payload = json.dumps({"type": "metaAndAssetCtxs"})
        headers = {'content-type': 'application/json'}
        response = requests.request("POST", url, headers=headers, data=payload)

        hyper = response.json()
        universe = hyper[0]['universe']
        funding = hyper[1]

        result = {}

        for idx in range(0,len(universe)):
            
            coin = universe[idx]['name']
            market_data = funding[idx]
            if coin in coins or coin.replace('k','') in coins:
                result[coin] = market_data

        return result


    def place_order(self,coin:str,size:float,is_buy:bool):
        # Place market order
        order_result = self.exchange.market_open(coin=coin, is_buy=is_buy, sz=size)
        return order_result
        
    
    def place_tpsl(self,coin:str,size:float,is_buy:bool,low_price:float,high_price:float):
        take_price = high_price if is_buy else low_price
        stop_price = low_price if is_buy else high_price
        # place sl
        stop_result = self.place_sl(coin=coin,size=size,is_buy=is_buy,price=stop_price)
        # place tp
        take_result = self.place_tp(coin=coin,size=size,is_buy=is_buy,price=take_price) 
        
        return order_result,stop_result,take_result


    def place_sl(self,coin:str,size:float,is_buy:bool,price:float):
        trigger_price = round_price(price,max_sig_figs=5, max_decimals=6)

        stop_order_type = {"trigger": {"triggerPx": trigger_price, "isMarket": True, "tpsl": "sl"}}
        stop_result = self.exchange.order(coin=coin, is_buy=not is_buy, sz=size, limit_px=trigger_price, order_type=stop_order_type, reduce_only=True)
        return stop_result

    def place_tp(self,coin:str,size:float,is_buy:bool,price:float):
        trigger_price = price*(.97) if not is_buy else price*(1.03)
        trigger_price = round_price(trigger_price,max_sig_figs=5, max_decimals=6)
        tp_order_type = {"trigger": {"triggerPx": trigger_price, "isMarket": True, "tpsl": "tp"}}
        take_result = self.exchange.order(coin=coin, is_buy=not is_buy, sz=size, limit_px=trigger_price, order_type=tp_order_type, reduce_only=True)
        return take_result

    def close_position(self,coin:str):
        order_result = self.exchange.market_close(coin)
        # TODO close out tpsl's
        return order_result

    def withdraw(self,amount:float):
        withdraw_result = self.exchange.withdraw_from_bridge(amount, self.ADDRESS)
        print(withdraw_result)


    def deposit(self,amount:float) -> None:
        # Connect to the Arbitrum node
        web3 = Web3(Web3.HTTPProvider(self.NODE_URL))
        web3.middleware_onion.inject(geth_poa_middleware, layer=0)  # Needed for some Ethereum testnets and sidechains like Arbitrum

        # Check connection
        if not web3.is_connected():
            print("Failed to connect to the Ethereum network!")
            exit()

        # Define the ABI for the ERC20 transfer function
        abi = [
            {
                "constant": False,
                "inputs": [
                    {
                        "name": "_to",
                        "type": "address"
                    },
                    {
                        "name": "_value",
                        "type": "uint256"
                    }
                ],
                "name": "transfer",
                "outputs": [
                    {
                        "name": "",
                        "type": "bool"
                    }
                ],
                "payable": False,
                "stateMutability": "nonpayable",
                "type": "function"
            },
        ]

        # Setup the contract
        contract = web3.eth.contract(address=self.USDC_CONTRACT_ADDRESS, abi=abi)

        # Transaction details
        tx = {
            'chainId': 42161,  # Arbitrum One chain ID
            'gas': 200000,
            'gasPrice': web3.eth.gas_price,
            'nonce': web3.eth.get_transaction_count(self.ADDRESS),
        }

        # Create transaction
        usdc_transfer = contract.functions.transfer(
            self.HYPER_ADDRESS,
            int(amount * (10**6))
        ).build_transaction(tx)

        # Sign the transaction
        signed_tx = web3.eth.account.sign_transaction(usdc_transfer, private_key=self.SECRET_KEY)

        # Send the transaction
        tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)

        # Print the transaction hash
        print(f'Transaction hash: {tx_hash.hex()}')


if __name__ == '__main__':
    # hyper_order(coin='ETH',size=0.01,is_buy=True)
    # hyper_withdraw(amount=1.5)
    client = HyperLiquidClient()
    order_result,stop_result,take_result = client.place_order(coin='ETH',size=0.01,is_buy=True,)
    print(order_result)
    print(stop_result)
    print(take_result)



