import os
import asyncio
from decimal import *
from aevo_sdk.aevo_client import AevoClient
from hyper_liquid_client import HyperLiquidClient
import pandas as pd
from loguru import logger
from datetime import datetime
### rebalance ###
from rebalance import rebalance
### utils ###
from trading_utils import get_quantity,calculate_proximity_to_liquidation

### websockets ###
from hyper_websocket import HyperLiquidWebSocket
from aevo_sdk.aevo_websocket import AevoWebSocket

#### telegram ####
from telegram_manager import TelegramManager


class TradingBot:
    def __init__(self):
        self.hyper_client = HyperLiquidClient() 
        self.aevo_client = AevoClient()
        self.telegram_manager = TelegramManager()
        self.coins = ['BTC','ETH','SOL','DOGE']
        self.hyper_ws = HyperLiquidWebSocket(message_callback=self.process_hyper_message)
        self.aevo_ws = AevoWebSocket(message_callback=self.process_aevo_message,coins=self.coins)
        self.ws_started = False
        self.leverage = 20
        self.threshold = 0.01
        self.profitability_threshold = 0.02
        self.position_coin = None
        self.has_position = None
        self.hyper_account = None
        self.hyper_position = None
        self.aevo_account = None
        self.aevo_position = None
        self.fundings = {}
        self.df = pd.DataFrame(columns=['coin', 'hyper_funding_rate', 'aevo_funding_rate', 'funding_rate_spread', 'hyper_price', 'aevo_price', 'pnl', 'hours_needed','instrument_id','buyer','open_position','hyper_side','aevo_side','hyper_liquidation_px','aevo_liquidation_px'])
        self.lock = asyncio.Lock()  # Initialize the lock
        self.hyper_value = 0.0
        self.aevo_value = 0.0
        self.value_df = pd.DataFrame(columns=['timestamp','aevo_value','hyper_value','total_value'])
        self.value_log_file = 'account_values.csv'
        self.load_value_df() 

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

        self.hyper_value = float(self.hyper_account['marginSummary']['accountValue'])
        self.aevo_value = float(self.aevo_account['equity'])
        self.update_value()
        # send a message to telegram
        # logger.info('sending telegram message on accounts')
        # await self.telegram_manager.send_acc_message()

        if 'assetPositions' in self.hyper_account and self.hyper_account['assetPositions']:
            self.hyper_position = self.hyper_account['assetPositions'][0]['position']
            self.position_coin = self.hyper_position['coin']
            self.hyper_side = 1 if float(self.hyper_position['szi']) < 0 else -1
            self.has_position = True
        else:
            self.hyper_position = None
            self.position_coin = None
            self.hyper_side = None
        # Ensure the 'positions' field exists and has at least one entry
        if 'positions' in self.aevo_account and self.aevo_account['positions']:
            self.aevo_position = self.aevo_account['positions'][0]
            self.aevo_side = -1 if self.hyper_position and float(self.hyper_position['szi']) < 0 else 1
            self.has_position = True
        else:
            self.aevo_position = None
            self.aevo_side = None

    async def process_hyper_message(self,msg):
        data = msg.get('data',{})
        if msg.get('channel') == 'activeAssetCtx':
            ctx = data.get('ctx')
            if not ctx: return
            coin = data['coin']
            mark_price = float(ctx['markPx'])
            funding_rate = float(ctx['funding'])
            self.fundings[coin] = self.fundings.get(coin, {})
            self.fundings[coin]['hyper_mark_price'] = mark_price
            self.fundings[coin]['hyper_funding_rate'] = funding_rate
            await self.funding_bot_main(coin)
        elif msg.get('channel') == 'webData2':
            try:
                clearing_house_state = data['clearinghouseState']
                # to get active posiition
                position = clearing_house_state['assetPositions'][0].get('position')
                if not position: return 
                coin = position['coin']
                self.fundings[coin] = self.fundings.get(coin, {})
                liquidation_price = position['liquidationPx']
                self.fundings[coin]['hyper_liquidation_px'] = liquidation_price
                await self.funding_bot_main(coin)
            except Exception as e:
                logger.info(f"Error with Hyper WebData2 {e}")



    async def process_aevo_message(self,msg):
        data = msg.get('data',{})
        # for api funding rate hits
        if msg.get('type') == 'funding':
            for funding_coin , funding_rate in data.items():
                self.fundings[funding_coin] = self.fundings.get(funding_coin, {})
                self.fundings[funding_coin]['aevo_funding_rate'] = funding_rate
                await self.funding_bot_main(funding_coin)
        elif msg.get('channel') == 'positions':
            try:
                position = data['positions'][0]
                if not position: return 
                coin = position['asset']
                self.fundings[coin] = self.fundings.get(coin, {})
                liquidation_price = position['liquidation_price']
                self.fundings[coin]['aevo_liquidation_px'] = liquidation_price
                await self.funding_bot_main(coin)
            except:
                pass
        elif not isinstance(data,dict): return
        else:
            tickers = data.get('tickers',[])
            if not tickers: return
            ticker = tickers[0]
            instrument_id = ticker['instrument_id']
            coin = ticker['instrument_name'].split('-')[0]
            mark_price = float(ticker['mark']['price'])
            self.fundings[coin] = self.fundings.get(coin, {})
            self.fundings[coin]['aevo_mark_price'] = mark_price
            self.fundings[coin]['instrument_id'] = instrument_id
            await self.funding_bot_main(coin)

    def load_value_df(self):
        if os.path.exists(self.value_log_file):
            self.value_df = pd.read_csv(self.value_log_file)
        else:
            self.value_df = pd.DataFrame(columns=['timestamp', 'aevo_value', 'hyper_value', 'total_value'])

    def save_value_df(self):
        self.value_df.to_csv(self.value_log_file, index=False)

    ### to see my profit's
    def update_value(self):
        total_value = self.hyper_value + self.aevo_value
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_row = pd.DataFrame([[timestamp, self.aevo_value, self.hyper_value, total_value]], columns=self.value_df.columns)
        self.value_df = pd.concat([self.value_df, new_row], ignore_index=True)
        self.save_value_df()
        logger.info(f"Updated account values: {new_row}")


    def get_profitablity(self,hyper_mark_price,aevo_mark_price,buyer):
        if buyer == 'AEVO':
            percent_pnl = (hyper_mark_price - aevo_mark_price) / aevo_mark_price
        elif buyer == 'HYPER_LIQUID':
            percent_pnl = (aevo_mark_price - hyper_mark_price) / hyper_mark_price 

        total_pnl = percent_pnl - self.hyper_client.TAKER_FEE - self.aevo_client.TAKER_FEE
        return total_pnl

    async def funding_bot_main(self, coin):
        pos = self.fundings.get(coin, {})
        if 'hyper_mark_price' in pos and 'hyper_funding_rate' in pos and 'aevo_mark_price' in pos and 'aevo_funding_rate' in pos:

            instrument_id = pos['instrument_id']
            hyper_mark_price = pos['hyper_mark_price']
            hyper_funding_rate = pos['hyper_funding_rate']
            aevo_mark_price = pos['aevo_mark_price']
            aevo_funding_rate = pos['aevo_funding_rate']

            if hyper_funding_rate >= aevo_funding_rate:
                spread = hyper_funding_rate - aevo_funding_rate
                total_pnl = self.get_profitablity(hyper_mark_price=hyper_mark_price,aevo_mark_price=aevo_mark_price,buyer='AEVO')
            elif hyper_funding_rate < aevo_funding_rate:
                spread = aevo_funding_rate - hyper_funding_rate
                total_pnl = self.get_profitablity(hyper_mark_price=hyper_mark_price,aevo_mark_price=aevo_mark_price,buyer='HYPER_LIQUID')

            hours_needed = (total_pnl * -1) / spread

            pos_coin_is_coin = coin == self.position_coin

            result = {
                'coin': coin,
                'hyper_funding_rate': hyper_funding_rate,
                'aevo_funding_rate': aevo_funding_rate,
                'funding_rate_spread': spread,
                'hyper_price': hyper_mark_price,
                'aevo_price': aevo_mark_price,
                'pnl': total_pnl,
                'hours_needed': hours_needed,
                'instrument_id' : instrument_id, 
                'buyer': 'AEVO' if hyper_funding_rate > aevo_funding_rate else 'HYPER_LIQUID',
                'open_position': pos_coin_is_coin,
                'hyper_side' : self.hyper_side if pos_coin_is_coin else 0,
                'aevo_side' : self.aevo_side if pos_coin_is_coin else 0,
                'hyper_liquidation_px' : pos.get('hyper_liquidation_px',0),
                'aevo_liquidation_px' : pos.get('aevo_liquidation_px',0)
            }

            self.update_dataframe(result)
            await self.check_enter_or_exit()

    def update_dataframe(self, result):
        # Ensure the result does not contain empty or all-NA entries
        if pd.notna(result['coin']):
            if result['coin'] in self.df['coin'].values:
                # Update the existing row
                self.df.loc[self.df['coin'] == result['coin'], self.df.columns != 'coin'] = pd.Series(result).drop('coin').values
            else:
                # Append a new row
                new_row = pd.DataFrame([result])
                self.df = pd.concat([self.df, new_row], ignore_index=True)
    
    async def check_enter_or_exit(self):
        # Ensure this section is not executed concurrently
        async with self.lock:
            if not self.df.empty:
                # print(self.df[['coin','hyper_funding_rate','aevo_funding_rate','hyper_price','aevo_price','pnl','funding_rate_spread']])
                # Find the row with the maximum PNL
                if not self.has_position:
                    max_pnl_row = self.df.loc[self.df['hours_needed'].idxmin()]
                    if max_pnl_row['pnl'] > 0:
                        logger.info("\nRow with the best hours:")
                        logger.info(max_pnl_row)
                        self.has_position = True
                        await self.open_positions(row=max_pnl_row)
                # check to see if the funding rate has gone negative and check liquidation
                elif self.has_position:
                    open_position_rows = self.df[self.df['open_position'] == True]
                    await self.check_liquidation(open_position_rows)
                    await self.check_negative_funding_rate(open_position_rows)
                    

    async def check_negative_funding_rate(self,open_position_rows):
        # check to see the position coin
        for _, row in open_position_rows.iterrows():
            who_bought = 'HYPER_LIQUID' if row['hyper_side'] == -1 else 'AEVO'
            buyer = row['buyer']
            if (buyer != who_bought):
                total_pnl = self.get_profitablity(row['hyper_price'], row['aevo_price'], row['buyer'])
                current_time = datetime.now()
                minutes = current_time.minute
                if total_pnl > 0:
                    logger.info(f"Closing profitbale position {total_pnl}")
                    await self.close_rebalance_start()
                    await self.telegram_manager.send_message(message=f" Closing Profitbale Price Because of Negative Funding Rates\n Hyper Price: {row['hyper_price']}\n Aevo Price: {row['aevo_price']}\n PNL: {total_pnl}")
                elif minutes >= 58:
                    logger.info("Closing position at 58-minute mark of the hour.")
                    await self.close_rebalance_start()
                    await self.telegram_manager.send_message(message=f" Closing Because of Negative Funding Rates and greater than 58 minute mark\n Hyper Price: {row['hyper_price']}\n Aevo Price: {row['aevo_price']}\n PNL: {total_pnl}")

    async def check_liquidation(self, open_position_rows):
        for _, row in open_position_rows.iterrows():
            if not row['hyper_liquidation_px'] or not row['aevo_liquidation_px']: continue 
            hyper_price = row['hyper_price']
            aevo_price = row['aevo_price']
            hyper_liquidation_price = float(row['hyper_liquidation_px'])
            aevo_liquidation_price = float(row['aevo_liquidation_px'])
            for platform in ('hyper','aevo'):
                mark_price = hyper_price if platform == 'hyper' else aevo_price
                liquidation_price = hyper_liquidation_price if platform == 'hyper' else aevo_liquidation_price
                percent_to_liquidation = calculate_proximity_to_liquidation(mark_price=mark_price, liquidation_price=liquidation_price)
                # first check if I need to close NOW
                if percent_to_liquidation <= self.threshold:
                    logger.info(f"Critical liquidation risk acting!")
                    await self.close_rebalance_start()
                    await self.telegram_manager.send_message(message=f' Critical Liquidation on {platform}/n Price is {percent_to_liquidation} away from liquidation/n Mark Price: {mark_price}/n Liquidation Price: {liquidation_price}')
                # else if it's getting close check if I can close profitbale
                elif percent_to_liquidation <= self.profitability_threshold:
                    total_pnl = self.get_profitablity(hyper_price, aevo_price, row['buyer'])
                    if total_pnl > 0:
                        logger.info(f"Closing profitbale position {total_pnl}")
                        await self.close_rebalance_start()
                        await self.telegram_manager.send_message(message=f' Closing Profitbale Price Because of Liquidation on {platform}/n Price is {percent_to_liquidation} away from liquidation/n Mark Price: {mark_price}/n Liquidation Price: {liquidation_price}\n PNL {total_pnl}')
                
            
    async def close_rebalance_start(self):
        instrument_id = self.aevo_position['instrument_id']
        aevo_opposite_side = False if self.aevo_position['side'] == 'buy' else True
        quantity = float(self.aevo_position['amount'])
        hyper_close_result = self.hyper_client.close_position(coin=self.hyper_position['coin'])
        aevo_close_result = self.aevo_client.place_order(instrument_id=instrument_id,is_buy=aevo_opposite_side,reduce_only=True,quantity=quantity)
        
        logger.info(f'Hyper Close Result: {hyper_close_result}')
        logger.info(f'Aevo Close Result: {aevo_close_result}')

        await self.telegram_manager.send_message(message='Hyper Close Result /n' + str(hyper_close_result))
        await self.telegram_manager.send_message(message='Aevo Close Result/n' + str(aevo_close_result))

        await self.get_accounts() 
        # await self.rebalance()
        # await self.start()

    async def rebalance(self):    
        #### re balance #####
        # check and update balances again # 
        await self.get_accounts()
        await rebalance(hyper_client=self.hyper_client,aevo_client=self.aevo_client,hyper_account=self.hyper_account,aevo_account=self.aevo_account)

        # self.funding_rates()
        # self.open_positions() 
    
    async def async_place_order(self,client, **kwargs):
        return client.place_order(**kwargs)
    
    async def async_place_tpsl(self,client, **kwargs):
        return client.place_tpsl(**kwargs)

    async def open_positions(self,row):
        coin = row['coin']
        buyer = row['buyer']
        instrument_id = row['instrument_id']
        hyper_balance = float(self.hyper_account['withdrawable'])*.9 # testing using 10%
        hyper_liquid_mark_price = row['hyper_price'] 
        hyper_size = get_quantity(leverage=self.leverage,price=hyper_liquid_mark_price,balance=hyper_balance,coin=coin)
        
        aevo_balance = float(self.aevo_account['collaterals'][0]['available_balance'])*.9 # testing using 10%
        aevo_mark_price = row['aevo_price']
        aevo_size = get_quantity(leverage=self.leverage,price=aevo_mark_price,balance=aevo_balance,coin=coin)
        
        size = min(hyper_size,aevo_size)

        hyper_order = self.async_place_order(self.hyper_client,coin=coin,size=size,is_buy=buyer == 'HYPER_LIQUID')
        aevo_order = self.async_place_order(self.aevo_client,instrument_id=instrument_id,is_buy=buyer == 'AEVO',reduce_only=False,quantity=size,)
        
        # hit them currently
        hyper_result , aevo_result = await asyncio.gather(hyper_order, aevo_order)

        logger.info(f'Hyper Order Result {hyper_result}')
        logger.info(f'Aevo Order Result {aevo_result}')

        await self.telegram_manager.send_message(message='Hyper Order Result /n' + str(hyper_result))
        await self.telegram_manager.send_message(message='Aevo Order Result/n' + str(aevo_result))

        # # get avg prices for both
        # avg_hyper_price = float(hyper_result['response']['data']['statuses'][0]['filled']['avgPx'])
        # avg_aevo_price = float(aevo_result['avg_price'])

        # # then set up stop loss and take profit based on top and bottom
        # low_price = avg_hyper_price if avg_hyper_price < avg_aevo_price else avg_aevo_price
        # high_price = avg_hyper_price if avg_hyper_price > avg_aevo_price else avg_aevo_price

        # low_price = low_price*(1.03)
        # high_price = high_price*(.97)

        # hyper_tpsl = self.async_place_tpsl(self.hyper_client,coin=coin,size=size,is_buy=buyer == 'HYPER_LIQUID',low_price=low_price,high_price=high_price)
        # aevo_tpsl = self.async_place_tpsl(self.aevo_client,instrument_id=instrument_id,is_buy=buyer == 'AEVO',quantity=size,low_price=low_price,high_price=high_price)

        # hyper_tpsl_result , aevo_tpsl_result = await asyncio.gather(hyper_tpsl, aevo_tpsl)

        # get the accounts again to update df
        await self.get_accounts()

    async def stop(self):
        await self.hyper_ws.stop()
        await self.aevo_ws.stop()
        self.ws_started = False

if __name__ == '__main__':
    bot = TradingBot()
    asyncio.run(bot.start())