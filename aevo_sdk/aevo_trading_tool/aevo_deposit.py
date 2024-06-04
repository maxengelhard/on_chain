from typing import List
import asyncio

from asyncio import (
    create_task,
    gather,
    run,
)

from .src.aevo.aevo import Aevo

from dotenv import load_dotenv
import os

from .config import (
    DEPOSIT_PERCENTAGE,
    CLOSE_POSITIONS,
    USE_PERCENTAGE,
    OPEN_POSITIONS,
    DEPOSIT_AMOUNT,
    TOKEN,
)

async def process_tasks(amount:float) -> List[asyncio.Task]:
    dotenv_path = os.path.join(os.path.dirname(__file__),'..','..', '.env')
    load_dotenv(dotenv_path=dotenv_path)
    trader = Aevo(
        private_key=os.getenv('private_key'),
        open_positions=False,
        close_positions=False,
        token=TOKEN,
        deposit_amount=amount,
        use_percentage=USE_PERCENTAGE,
        deposit_percentage=DEPOSIT_PERCENTAGE
    )
    deposit_task = create_task(trader.deposit())
    await deposit_task
    return [deposit_task]


async def aevo_deposit(amount:float) -> None:
    tasks = []
    tasks.extend(await process_tasks(amount=amount))

    await gather(*tasks)


if __name__ == '__main__':
    run(aevo_deposit(amount=1))
