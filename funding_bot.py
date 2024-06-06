import asyncio
from datetime import datetime, timedelta
from aevo_sdk.aevo_client import AevoClient
from hyper_liquid_client import HyperLiquidClient
### rebalance ###
from rebalance import rebalance
### utils ###
from trading_utils import calculate_proximity_to_liquidation,get_quantity

### websockets ###
from hyper_websocket import HyperLiquidWebSocket
from aevo_sdk.aevo_websocket import AevoWebSocket


class TradingBot:
    def __init__(self):
        self.hyper_client = HyperLiquidClient() 
        self.aevo_client = AevoClient()
        self.threshold = 0.02
        self.hyper_ws = HyperLiquidWebSocket(message_callback=self.process_hyper_message)
        self.aevo_ws = AevoWebSocket(message_callback=self.process_aevo_message)
        self.ws_started = False
        self.coins = ['ETH','BTC','SOL','DOGE']
        self.leverage = 10
        self.hyper_position = None
        self.aevo_position = None
        self.position_coin = None
        self.hyper_funding = None
        self.aevo_funding = None
        self.hyper_funding_rate = None
        self.aevo_funding_rate = None
        self.hyper_side = None
        self.aevo_side = None
        self.max_coin = None
        self.negative_since = None  # Track when the spread first went negative
        self.rebalance_triggered = False  # Ensure we don't trigger rebalance repeatedly

    async def start(self):
        await self.get_accounts()
        while not self.ws_started:
            if self.position_coin and not self.ws_started:
                await asyncio.gather(
                    self.hyper_ws.start(coin=self.position_coin),
                    self.aevo_ws.start(coin=self.position_coin)
                )
                self.ws_started = True
            elif not self.position_coin and self.ws_started:
                await self.stop()
                self.ws_started = False
            await asyncio.sleep(1)
        
    async def get_accounts(self):
        # Load positions from both platforms
        self.hyper_account = self.hyper_client.get_account()
        self.aevo_account = await self.aevo_client.get_account()

        if 'assetPositions' in self.hyper_account and self.hyper_account['assetPositions']:
            self.hyper_position = self.hyper_account['assetPositions'][0]['position']
            self.position_coin = self.hyper_position['coin']
            self.hyper_side = 1 if float(self.hyper_position['szi']) < 0 else -1
        else:
            self.hyper_position = None
            self.position_coin = None
            self.hyper_side = None
        # Ensure the 'positions' field exists and has at least one entry
        if 'positions' in self.aevo_account and self.aevo_account['positions']:
            self.aevo_position = self.aevo_account['positions'][0]
            self.aevo_side = -1 if self.hyper_position and float(self.hyper_position['szi']) < 0 else 1
        else:
            self.aevo_position = None
            self.aevo_side = None

    async def process_hyper_message(self,msg):
        data = msg.get('data',{}) 
        ctx = data.get('ctx')
        if not ctx: return
        mark_price = float(ctx['markPx'])
        await self.check_liquidation(mark_price=mark_price,platform='hyper')
        self.hyper_funding_rate = float(ctx['funding']) * self.hyper_side
        await self.check_funding_rates()


    async def process_aevo_message(self,msg):
        data = msg.get('data',{})
        if not isinstance(data,dict): return
        tickers = data.get('tickers',[])
        if not tickers: return
        ticker = tickers[0]
        mark_price = float(ticker['mark']['price'])
        await self.check_liquidation(mark_price=mark_price,platform='aevo')
        self.aevo_funding_rate = float(ticker['funding_rate']) * self.aevo_side
        await self.check_funding_rates()

    async def check_funding_rates(self):
        if self.hyper_funding_rate and self.aevo_funding_rate:
            total_funding_rate = self.hyper_funding_rate + self.aevo_funding_rate
            current_time = datetime.now()
            # check to see if it's been negative for an hour
            if total_funding_rate < 0:
                print(f"Negative funding rates. Checking for negative since")
                if not self.negative_since:
                    self.negative_since = current_time
                elif current_time - self.negative_since >= timedelta(hours=1) and not self.rebalance_triggered:
                    print('would close')
                    # await self.close_rebalance_start()
            else:
                self.negative_since = None
                self.rebalance_triggered = False 

    async def check_liquidation(self, mark_price, platform):
        liquidation_price = None
        if platform == 'hyper': liquidation_price = float(self.hyper_position['liquidationPx'])
        elif platform == 'aevo': liquidation_price = float(self.aevo_position['liquidation_price'])
        percent_to_liquidation = calculate_proximity_to_liquidation(mark_price=mark_price, liquidation_price=liquidation_price)
        # print(f'checking liquidation on {platform}. Current %:{percent_to_liquidation}')
        if abs(percent_to_liquidation) < self.threshold:
            print(f"Critical liquidation risk on {platform}, acting!")
            await self.close_rebalance_start()
            
    async def close_rebalance_start(self):
        await self.stop()
        instrument_id = self.aevo_position['instrument_id']
        aevo_opposite_side = False if self.aevo_position['side'] == 'buy' else True
        quantity = float(self.aevo_position['amount'])
        self.hyper_client.close_position(coin=self.hyper_position['coin'])
        await self.aevo_client.create_order(instrument_id=instrument_id,is_buy=aevo_opposite_side,reduce_only=True,quantity=quantity)
        await self.rebalance()
        await self.start()

    async def rebalance(self):    
        #### re balance #####
        # check and update balances again # 
        await self.get_accounts()
        balanced = await rebalance(hyper_client=self.hyper_client,aevo_client=self.aevo_client,hyper_account=self.hyper_account,aevo_account=self.aevo_account) 
        if balanced:
            self.funding_rates()
            await self.open_positions()
            self.negative_since = None
            self.rebalance_triggered = False 

    def funding_rates(self):
        self.hyper_funding = self.hyper_client.get_funding(coins=self.coins)
        self.aevo_funding = self.aevo_client.get_funding(coins=self.coins)
        highest_rates = {
            coin: {
                'Highest Long Rate': (-float('inf'), None),
                'Highest Short Rate': (-float('inf'), None)
            }
            for coin in self.coins
        }
        for coin in self.coins:
            aevo_coin = float(self.aevo_funding[coin]) * 100
            hyper_coin = float(self.hyper_funding[coin]['funding'])*100  # Assuming 'funding' is meant to be 'furniture'

            data_sources = {
                'AEVO': {'long_rate': -aevo_coin, 'short_rate': aevo_coin},
                'HYPER_LIQUID': {'long_rate': -hyper_coin, 'short_rate': hyper_coin}
            }

            for source, rates in data_sources.items():
                long_rate = rates['long_rate'] * 8760
                short_rate = rates['short_rate'] * 8760

                if long_rate > highest_rates[coin]['Highest Long Rate'][0]:
                    highest_rates[coin]['Highest Long Rate'] = (long_rate, source)

                if short_rate > highest_rates[coin]['Highest Short Rate'][0]:
                    highest_rates[coin]['Highest Short Rate'] = (short_rate, source)

        # Calculate the maximum spread correctly
        max_spread = max(
            (abs(rates['Highest Long Rate'][0] + rates['Highest Short Rate'][0]) for rates in highest_rates.values()),
            default=0
        )

        # Find the coin with the maximum spread
        self.max_coin = max(
            (coin for coin, rates in highest_rates.items() if abs(rates['Highest Long Rate'][0] + rates['Highest Short Rate'][0]) == max_spread),
            default=None
        )

        # Extract the details for the maximum spread coin
        max_long_rate, self.max_dex_long = highest_rates[self.max_coin]['Highest Long Rate']
        max_short_rate, self.max_dex_short = highest_rates[self.max_coin]['Highest Short Rate']

        # Output the results
        print('#### Highest Spread ####')
        print(self.max_coin)
        print(f'Highest Long Rate: {max_long_rate:.12f} from {self.max_dex_long}')
        print(f'Highest Short Rate: {max_short_rate:.12f} from {self.max_dex_short}')
        print(f'Spread: {max_spread:.12f}')


    async def open_positions(self):
        hyper_balance = float(self.hyper_account['withdrawable'])
        hyper_liquid_mark_price = float(self.hyper_funding[self.max_coin]['markPx']) 
        hyper_size = get_quantity(leverage=self.leverage,price=hyper_liquid_mark_price,balance=hyper_balance)
        
        aevo_balance = float(self.aevo_account['collaterals'][0]['available_balance'])
        aevo_market_data = await self.aevo_client.get_markets(asset=self.max_coin,instrument='PERPETUAL')
        aevo_current_mark_price = float(aevo_market_data[0]['mark_price'])
        aevo_size = get_quantity(leverage=self.leverage,price=aevo_current_mark_price,balance=aevo_balance)
        
        if self.max_dex_long == 'AEVO':
            print(f'long_aevo with {self.max_coin}')
            await self.aevo_client.create_order(instrument_id=1,is_buy=True,reduce_only=False,quantity=aevo_size)
            print(f'short hyper with {self.max_coin}')
            self.hyper_client.place_order(coin=self.max_coin,size=hyper_size,is_buy=False)

        elif self.max_dex_long == 'HYPER_LIQUID':
            print(f'long hyper with {self.max_coin}')
            self.hyper_client.place_order(coin=self.max_coin,size=hyper_size,is_buy=True)
            print(f'short aevo with {self.max_coin}')
            await self.aevo_client.create_order(instrument_id=1,is_buy=False,reduce_only=False,quantity=aevo_size)
     

    async def stop(self):
        await self.hyper_ws.stop()
        await self.aevo_ws.stop()
        self.ws_started = False


if __name__ == '__main__':
    bot = TradingBot()
    asyncio.run(bot.start())