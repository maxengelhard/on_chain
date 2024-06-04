from gmx_python_sdk.scripts.v2.get_funding_apr import GetFundingFee
from gmx_python_sdk.scripts.v2.get_borrow_apr import GetBorrowFee

def gmx_borrow_funding(coins: list) -> dict:
    # Create an instance of the class, specify the chain as required by the constructor
    funding_fee = GetFundingFee(chain='arbitrum')
    borrow_fee = GetBorrowFee(chain='arbitrum')

    # Now call the method on the instance
    funding_apr = funding_fee.get_funding_apr(to_json=False, to_csv=False)
    borrow_apr = borrow_fee.get_borrow_apr(to_json=False,to_csv=False)

    # Prepare a dictionary to store the rates for each specified coin
    rates = {}

    # Process each coin in the input dictionary
    for coin in coins:
        if coin in funding_apr['long']:
            long_rate = funding_apr['long'].get(coin, 0) - borrow_apr['long'].get(coin,0)
            short_rate = funding_apr['short'].get(coin, 0) - borrow_apr['short'].get(coin,0)
            # Store the calculated rates for each coin
            rates[coin] = {
                'long_rate': long_rate,
                'short_rate': short_rate
            }

    return rates

if __name__ == '__main__':
    specified_coins = ['ETH']  # Specify the coins you want to check
    coin_rates = gmx_borrow_funding(specified_coins)
    print(coin_rates)
