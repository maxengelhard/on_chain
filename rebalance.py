import asyncio
import time
# hyper functions
# aevo functions
from eth_account_client import EthAccountClient
# util
from trading_utils import amount_to_withdraw


async def rebalance(hyper_client,aevo_client,hyper_account,aevo_account):
    eth_account_client = EthAccountClient()
    print('need to rebalance')
    # closed out
    # get account values for each
    aevo_balance = float(aevo_account['balance'])
    hyper_balance = float(hyper_account['withdrawable'])

    # get the difference from both
    difference = hyper_balance - aevo_balance

    account_balance = 0
    if difference > 1:
        # withdraw from hyper and deposit to aevo
        withdraw_amount = amount_to_withdraw(higher_value=hyper_balance,lower_value=aevo_balance) + 1 # for fee
        # withdraw this amount from hyper
        # with withdraw usdc
        print('withdrawing hyper')
        hyper_client.withdraw(amount=withdraw_amount)
        while account_balance ==0:
            account_balance = eth_account_client.get_usdc_balance(is_usdc=True)
            print(f'checking account balance {account_balance}')
            if account_balance >0: break
            else: time.sleep(60)

        ### need to swap to usdc.e ###
        print('swapping coins')
        eth_account_client.swap_usdc(to_usdc=False,amount=account_balance)

        new_account_balance = eth_account_client.get_usdc_balance(is_usdc=False)
        ### now that we have usdc.e deposit into aevo
        print(f'depositing {new_account_balance} into aevo')
        await aevo_client.deposit(amount=new_account_balance)


    elif difference < -1:
        # withdraw from aevo and deposit to hyper
        withdraw_amount = amount_to_withdraw(higher_value=aevo_balance,lower_value=hyper_balance)
        # withdraw this amount from aevo
        print('withdrawing from aevo')
        await aevo_client.withdraw(amount=withdraw_amount)
        # will withdraw usdc.e
        while account_balance == 0:
            account_balance = eth_account_client.get_usdc_balance(is_usdc=False)
            print(f'checking account balance {account_balance}')
            if account_balance >0: break
            else: time.sleep(60)
        ### need to swap to usdc
        eth_account_client.swap_usdc(to_usdc=True,amount=account_balance)
        ## have usdc deposit into hyper
        new_account_balance = eth_account_client.get_usdc_balance(is_usdc=True)
        print(f'depositing {new_account_balance} into hyper')
        hyper_client.deposit(amount=new_account_balance)