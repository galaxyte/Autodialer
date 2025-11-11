"""
Background task orchestration for processing queued call requests.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterable, List, Sequence
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..models.call_log import CallLog, CallStatus
from .twilio_service import CallResult, TwilioService


RATE_LIMIT_SECONDS = 2.5


@dataclass(slots=True)
class CallTask:
    """In-memory representation of a scheduled call."""

    id: int
    number: str
    message: str


async def enqueue_calls(
    numbers: Sequence[str],
    message: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> List[CallTask]:
    """
    Persist numbers to the database as queued calls and return their tasks.
    """

    tasks: List[CallTask] = []

    async with session_factory() as session:
        for number in numbers:
            log = CallLog(number=number, message=message, status=CallStatus.QUEUED)
            session.add(log)
            await session.flush()
            tasks.append(CallTask(id=log.id, number=log.number, message=log.message or ""))
        await session.commit()

    return tasks


async def execute_call_sequence(
    tasks: Iterable[CallTask],
    session_factory: async_sessionmaker[AsyncSession],
    twilio_service: TwilioService,
) -> None:
    """
    Iterate through the queued calls, trigger Twilio, and persist outcomes.
    """

    for task in tasks:
        await _update_status(
            task.id,
            CallStatus.IN_PROGRESS,
            session_factory,
        )
        await asyncio.sleep(RATE_LIMIT_SECONDS)
        try:
            result = await twilio_service.place_call(task.number, task.message)
        except ValueError as exc:
            await _update_status(
                task.id,
                CallStatus.SKIPPED,
                session_factory,
                error=str(exc),
            )
            continue
        await _finalise(task.id, result, session_factory)


async def _update_status(
    call_id: int,
    status: CallStatus,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    error: str | None = None,
) -> None:
    async with session_factory() as session:
        log = await session.get(CallLog, call_id)
        if not log:
            return
        log.mark(status, error=error)
        await session.commit()


async def _finalise(
    call_id: int,
    result: CallResult,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    status = CallStatus.SUCCESS if result.success else CallStatus.FAILED
    async with session_factory() as session:
        log = await session.get(CallLog, call_id)
        if not log:
            return
        log.mark(status, duration=result.duration, call_sid=result.sid, error=result.error)
        await session.commit()

