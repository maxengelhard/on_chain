import pandas as pd
from telegram import Bot
import os
import asyncio
from dotenv import load_dotenv

class TelegramManager:
    def __init__(self) -> None:
        load_dotenv()
        self.TOKEN = os.environ.get('telegram_bot_token')
        self.CHAT_ID = os.environ.get('telegram_chat_id')
        self.bot = Bot(token=self.TOKEN)
        self.acc_csv_file = 'account_values.csv'
        self.acc_df = None

    def load_values(self):
        self.acc_df = pd.read_csv(self.acc_csv_file)
        # Convert the 'timestamp' column to datetime
        self.acc_df['timestamp'] = pd.to_datetime(self.acc_df['timestamp'])

    def get_latest_values(self):
        # Get the latest values
        latest_data = self.acc_df.iloc[-1]
        latest_aevo_value = latest_data['aevo_value']
        latest_hyper_value = latest_data['hyper_value']
        latest_total_value = latest_data['total_value']
        return latest_total_value, latest_aevo_value, latest_hyper_value

    async def send_acc_message(self):
        self.load_values()
        total_value, aevo_value, hyper_value = self.get_latest_values()
        message = f"<b>Total Value: ${total_value:.2f}</b>\n"
        message += f"Aevo Value: ${aevo_value:.2f}\n"
        message += f"Hyper Value: ${hyper_value:.2f}"
        await self.send_message(message=message)
        
    async def send_message(self,message):
        await self.bot.send_message(chat_id=self.CHAT_ID, text=message, parse_mode='HTML')

# Execute the script
if __name__ == '__main__':
    manager = TelegramManager()
    manager.send_acc_message()
