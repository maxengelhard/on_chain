# On-Chain Funding Management Bot

This repository contains tools for automating funding rate spread management across perpetual futures exchanges. The primary script, `manager_bot.py`, monitors and executes strategies to capture arbitrage opportunities from funding rate spreads between Hyperliquid and Aevo.

## Features

- **Funding Rate Spread Arbitrage**: Identifies and captures spreads between funding rates on Hyperliquid and Aevo.
- **Error Management**: Utilizes `manager_bot.py` to handle websocket errors, which often occur around the 15-minute mark, ensuring uninterrupted operation.
- **Multi-Exchange Support**: Specifically designed for Hyperliquid and Aevo integration to optimize arbitrage opportunities.
- **Notification System**: Sends real-time updates and alerts through Telegram.

## Prerequisites

- **Python Version**: Requires Python 3.8 or higher.
- **Dependencies**: See `requirements.txt` for all required Python packages.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/maxengelhard/on_chain.git
   cd on_chain
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create an `.env` file with the required variables:
   ```plaintext
   private_key=
   address=
   aevo_api=
   aevo_secret=
   signing_key=
   rpc_end_point=
   usdc_contract=
   usdce_contract=
   hyper_liquid_address=
   aevo_address=
   binanceus_api_key=
   binanceus_secret=
   telegram_bot_token=
   telegram_chat_id=
   ```

## Configuration

- Populate the `.env` file with your specific API keys, secrets, and configuration details.
- Ensure accurate setup of blockchain RPC endpoints and contract addresses for both Hyperliquid and Aevo.

## Usage

Run the primary bot script to manage funding rate spreads:

```bash
python manager_bot.py
```

The `manager_bot.py` script:

- Continuously monitors funding rates on Hyperliquid and Aevo.
- Handles websocket errors, automatically restarting connections every 15 minutes to prevent disruptions.
- Executes trades to capture funding rate spreads, optimizing for profitability.

## Key Insights

The bot is specifically designed to exploit differences in funding rates between Hyperliquid and Aevo, enabling consistent arbitrage profits. By actively monitoring and balancing positions, it maximizes efficiency while mitigating risks associated with funding rate volatility.

## Caution

The bot is not profitable yet. Exchange fees for swapping between Hyperliquid and Aevo are high and funding rates vary.

## Telegram Notifications

Set up the `telegram_bot_token` and `telegram_chat_id` variables in the `.env` file to receive real-time updates and alerts on the bot's performance and error statuses.

## Disclaimer

This bot is provided for educational and research purposes only. Use it at your own risk. Ensure you understand the risks associated with trading on perpetual futures exchanges.
