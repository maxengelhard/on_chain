from typing import List
import asyncio

from asyncio import (
    create_task,
    gather,
    run,
)

from .src.aevo.aevo import Aevo

from .src.data import private_keys

from .config import (
    DEPOSIT_PERCENTAGE,
    CLOSE_POSITIONS,
    USE_PERCENTAGE,
    OPEN_POSITIONS,
    DEPOSIT_AMOUNT,
    TOKEN,
)


async def process_tasks(private_key: str,amount:float) -> List[asyncio.Task]:
    tasks = []
    trader = Aevo(
        private_key=private_key,
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
    for private_key in private_keys:
        tasks.extend(await process_tasks(private_key,amount=amount))

    await gather(*tasks)


if __name__ == '__main__':
    run(aevo_deposit(amount=1))
