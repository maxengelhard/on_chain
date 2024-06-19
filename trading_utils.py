import math

def calculate_proximity_to_liquidation(mark_price, liquidation_price):
    if liquidation_price < mark_price:  # Long position
        percent_to_liquidation = (liquidation_price - mark_price) / mark_price
    else:  # Short position
        percent_to_liquidation = (mark_price - liquidation_price) / liquidation_price
    return percent_to_liquidation

def amount_to_withdraw(higher_value:float,lower_value:float) -> None:
    mid_point = float((higher_value + lower_value)/2)
    return higher_value - mid_point

def get_quantity(leverage:int,price:float,balance:float,coin:str):
    size = balance / (price / leverage)
    if coin == 'DOGE':
        return math.floor(size)  # Floor to the nearest integer for DOGE
    else:
        return math.floor(size * 100) / 100  # Round to 2 decimal places for other coins