from uniswap import Uniswap
from web3 import Web3
import math
# Constants
import json
import os
from dotenv import load_dotenv


class EthAccountClient:
    def __init__(self) -> None:
        load_dotenv()
        self.ADDRESS = os.getenv('address') 
        self.PRIVATE_KEY = os.getenv('private_key')
        self.UNISWAP_VERSION = 3
        self.NODE_URL = os.getenv('rpc_end_point')
        self.USDC_CONTRACT_ADDRESS = Web3.to_checksum_address(os.getenv('usdc_contract'))
        self.USDCE_CONTRACT_ADDRESS = Web3.to_checksum_address(os.getenv('usdce_contract'))
        self.ERC20_ABI = self.load_json('aevo_sdk/abis/erc20.json')

    def load_json(self, filepath):
        with open(filepath, 'r') as file:
            return json.load(file)
        
    def swap_usdc(self,to_usdc:bool,amount:float):
        swap_amount = math.floor((amount * (10**6)))
        uniswap = Uniswap(address=self.ADDRESS, private_key=self.PRIVATE_KEY, version=self.UNISWAP_VERSION, provider=self.NODE_URL)
        token_in = self.USDCE_CONTRACT_ADDRESS if to_usdc else self.USDC_CONTRACT_ADDRESS
        token_out = self.USDC_CONTRACT_ADDRESS if to_usdc else self.USDCE_CONTRACT_ADDRESS 
        uniswap.make_trade(token_in, token_out, swap_amount,fee=500)  # sell 1 usdc for usdce 


    def get_usdc_balance(self,is_usdc:bool):
        contract_address = self.USDC_CONTRACT_ADDRESS if is_usdc else self.USDCE_CONTRACT_ADDRESS 
        # Ensure that the connection is established
        web3 = Web3(Web3.HTTPProvider(self.NODE_URL))
        if web3.is_connected():
            print("Successfully connected to the Ethereum node.")
            web3 = Web3(Web3.HTTPProvider(self.NODE_URL))
            usdc_contract = web3.eth.contract(address=contract_address, abi=self.ERC20_ABI)
            balance = usdc_contract.functions.balanceOf(Web3.to_checksum_address(self.ADDRESS)).call()
            return balance / 10**6  # Assuming USDC has 6 decimals
        else:
            print('error connecting')

if __name__ == '__main__':
    eth_client = EthAccountClient()
    usdc_balance = eth_client.get_usdc_balance(is_usdc=True)
    print(usdc_balance) 