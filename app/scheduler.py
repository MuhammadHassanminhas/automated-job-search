from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler


async def _discovery_tick() -> None:
    """Placeholder — wired in Phase B.2."""
    ...


async def _rank_tick() -> None:
    """Placeholder — wired in Phase B.2."""
    ...


async def _sender_tick() -> None:
    """Placeholder — wired in Phase B.2."""
    ...


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _discovery_tick,
        "interval",
        hours=6,
        id="scheduler.discovery.tick",
    )
    scheduler.add_job(
        _rank_tick,
        "interval",
        hours=1,
        id="scheduler.rank.tick",
    )
    scheduler.add_job(
        _sender_tick,
        "interval",
        seconds=30,
        id="scheduler.sender.tick",
    )
    return scheduler
