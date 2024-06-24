import math

def calculate_proximity_to_liquidation(mark_price, liquidation_price):
    if liquidation_price < mark_price:  # Long position
        percent_to_liquidation = (liquidation_price - mark_price) / mark_price
    else:  # Short position
        percent_to_liquidation = (mark_price - liquidation_price) / liquidation_price
    return abs(percent_to_liquidation)

def amount_to_withdraw(higher_value:float,lower_value:float) -> None:
    mid_point = float((higher_value + lower_value)/2)
    return higher_value - mid_point

def get_quantity(leverage:int,price:float,balance:float,coin:str):
    size = balance / (price / leverage)
    if coin == 'DOGE':
        return math.floor(size)  # Floor to the nearest integer for DOGE
    elif coin == 'SOL':
        return math.floor(size * 10) / 10 # Round to 1 decimal place
    else:
        return math.floor(size * 100) / 100  # Round to 2 decimal places for other coins
    

def round_price(price, max_sig_figs=5, max_decimals=6):
    if price == 0:
        return 0
    # Round to significant figures first
    rounded_price = round(price, max_sig_figs - len(str(int(price))))
    # Ensure it does not exceed max decimals
    return round(rounded_price, max_decimals)