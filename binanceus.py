import urllib.parse
import hashlib
import hmac
import base64
import requests
import time
import os
from dotenv import load_dotenv
import asyncio
import websockets


class BinanceUS:
    def __init__(self) -> None:
        load_dotenv()
        self.API_KEY = os.getenv('binanceus_api_key')
        self.SECRET=os.getenv('binanceus_secret')
        self.API_URL = "https://api.binance.us"
        self.headers =  {'X-MBX-APIKEY':self.API_KEY}

    # get binanceus signature
    def get_binanceus_signature(self,data):
        postdata = urllib.parse.urlencode(data)
        message = postdata.encode()
        byte_key = bytes(self.SECRET, 'UTF-8')
        mac = hmac.new(byte_key, message, hashlib.sha256).hexdigest()
        return mac

    # Attaches auth headers and returns results of a POST request
    def get_account(self):
        data = {"timestamp": int(round(time.time() * 1000)),}
        uri_path = "/api/v3/account"
        signature = self.get_binanceus_signature(data)
        params={
            **data,
            "signature": signature,
            }
        req = requests.get((self.API_URL + uri_path), params=params, headers=self.headers)
        return req.text

    # Attaches auth headers and returns results of a POST request
    def order_spot(self,uri_path, data, symbol,side,quantity):
        uri_path = "/api/v3/order"
        data = {
            "symbol": symbol,
            "side": side,
            "type": type,
            "quantity": quantity,
            "timestamp": int(round(time.time() * 1000))
        }
        payload={
            **data,
            "signature": self.get_binanceus_signature(data),
            }
        req = requests.post((self.API_URL + uri_path), headers=self.headers, data=payload)
        return req.text
    
    async def websocket(self):
        url = "wss://stream.binance.us:9443/stream?streams=!miniTicker@arr@3000ms"
        headers = {}

        async with websockets.connect(url, extra_headers=headers) as websocket:
            while True:
                message = await websocket.recv()
                print(message)
    
if __name__ == '__main__':
    binaanceus = BinanceUS()
    asyncio.run(binaanceus.websocket())