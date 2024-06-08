import asyncio
from decimal import *
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

    async def start(self):
        await self.get_accounts()
        await asyncio.gather(
            self.hyper_ws.start(coins=self.coins),
            self.aevo_ws.start(coins=self.coins)
        )
        
    async def get_accounts(self):
        # Load positions from both platforms
        self.hyper_account = self.hyper_client.get_account()
        self.aevo_account = await self.aevo_client.get_account()

        # if 'assetPositions' in self.hyper_account and self.hyper_account['assetPositions']:
        #     self.hyper_position = self.hyper_account['assetPositions'][0]['position']
        #     self.position_coin = self.hyper_position['coin']
        #     self.hyper_side = 1 if float(self.hyper_position['szi']) < 0 else -1
        # else:
        #     self.hyper_position = None
        #     self.position_coin = None
        #     self.hyper_side = None
        # # Ensure the 'positions' field exists and has at least one entry
        # if 'positions' in self.aevo_account and self.aevo_account['positions']:
        #     self.aevo_position = self.aevo_account['positions'][0]
        #     self.aevo_side = -1 if self.hyper_position and float(self.hyper_position['szi']) < 0 else 1
        # else:
        #     self.aevo_position = None
        #     self.aevo_side = None

    async def process_hyper_message(self,msg):
        data = msg.get('data',{}) 
        ctx = data.get('ctx')
        if not ctx: return
        mark_price = float(ctx['markPx'])
        self.hyper_mark_price = mark_price
        funding_rate = float(ctx['funding'])
        self.hyper_funding_rate = funding_rate
        self.check_profitablitlity()
        # await self.check_liquidation(mark_price=mark_price,platform='hyper')
        # self.hyper_funding_rate = float(ctx['funding']) * self.hyper_side
        # await self.check_funding_rates()


    async def process_aevo_message(self,msg):
        data = msg.get('data',{})
        if not isinstance(data,dict): return
        tickers = data.get('tickers',[])
        if not tickers: return
        ticker = tickers[0]
        mark_price = float(ticker['mark']['price'])
        self.aevo_mark_price = mark_price
        funding_rate = float(ticker['funding_rate'])
        self.aevo_funding_rate = funding_rate
        self.check_profitablitlity()
        # await self.check_liquidation(mark_price=mark_price,platform='aevo')
        # self.aevo_funding_rate = float(ticker['funding_rate']) * self.aevo_side
        # await self.check_funding_rates()

    def check_profitablitlity(self):
        if self.hyper_mark_price and self.hyper_funding_rate and self.aevo_funding_rate and self.aevo_mark_price:
            hyper_fees = self.hyper_client.TAKER_FEE
            aevo_fees = self.aevo_client.TAKER_FEE
            print(f'hyper funding rate: {self.hyper_funding_rate}')
            print(f'aevo funding rate: {self.aevo_funding_rate}')
            if self.hyper_funding_rate > self.aevo_funding_rate:
                # buy aevo
                spread = self.hyper_funding_rate - self.aevo_funding_rate
                percent_pnl = (self.hyper_mark_price - self.aevo_mark_price) / self.aevo_mark_price
            elif self.hyper_funding_rate < self.aevo_funding_rate:
                # buy hyper
                spread = self.aevo_funding_rate - self.hyper_funding_rate
                percent_pnl = (self.aevo_mark_price - self.hyper_mark_price) / self.hyper_mark_price
            total_pnl = percent_pnl - hyper_fees - aevo_fees
            print(f'funding spread {spread:12f}')
            print(f'{total_pnl:12f}')
            print(f'hours needed {total_pnl*-1/spread}')

    async def check_funding_rates(self):
        if self.hyper_funding_rate and self.aevo_funding_rate:
            total_funding_rate = self.hyper_funding_rate + self.aevo_funding_rate
            if total_funding_rate < 0:
                await self.close_rebalance_start()

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
        await rebalance(hyper_client=self.hyper_client,aevo_client=self.aevo_client,hyper_account=self.hyper_account,aevo_account=self.aevo_account) 

        # self.funding_rates()
        # await self.open_positions() 

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


    
    # def get_current_profitability_after_fees(self, token: str, connector_1: str, connector_2: str, side: str):
    #     """
    #     This methods compares the profitability of buying at market in the two exchanges. If the side is TradeType.BUY
    #     means that the operation is long on connector 1 and short on connector 2.
    #     """
    #     trading_pair_1 = self.get_trading_pair_for_connector(token, connector_1)
    #     trading_pair_2 = self.get_trading_pair_for_connector(token, connector_2)

    #     connector_1_price = Decimal(self.market_data_provider.get_price_for_quote_volume(
    #         connector_name=connector_1,
    #         trading_pair=trading_pair_1,
    #         quote_volume=self.config.position_size_quote,
    #         is_buy=side == side,
    #     ).result_price)
    #     connector_2_price = Decimal(self.market_data_provider.get_price_for_quote_volume(
    #         connector_name=connector_2,
    #         trading_pair=trading_pair_2,
    #         quote_volume=self.config.position_size_quote,
    #         is_buy=side != side,
    #     ).result_price)
    #     estimated_fees_connector_1 = self.connectors[connector_1].get_fee(
    #         base_currency=trading_pair_1.split("-")[0],
    #         quote_currency=trading_pair_1.split("-")[1],
    #         order_type=OrderType.MARKET,
    #         order_side=TradeType.BUY,
    #         amount=self.config.position_size_quote / connector_1_price,
    #         price=connector_1_price,
    #         is_maker=False,
    #         position_action=PositionAction.OPEN
    #     ).percent
    #     estimated_fees_connector_2 = self.connectors[connector_2].get_fee(
    #         base_currency=trading_pair_2.split("-")[0],
    #         quote_currency=trading_pair_2.split("-")[1],
    #         order_type=OrderType.MARKET,
    #         order_side=TradeType.BUY,
    #         amount=self.config.position_size_quote / connector_2_price,
    #         price=connector_2_price,
    #         is_maker=False,
    #         position_action=PositionAction.OPEN
    #     ).percent

    #     if side == TradeType.BUY:
    #         estimated_trade_pnl_pct = (connector_2_price - connector_1_price) / connector_1_price
    #     else:
    #         estimated_trade_pnl_pct = (connector_1_price - connector_2_price) / connector_2_price
    #     return estimated_trade_pnl_pct - estimated_fees_connector_1 - estimated_fees_connector_2


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