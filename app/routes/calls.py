"""
FastAPI routes for uploading phone numbers, initiating call campaigns,
and rendering dashboard views for Autodialer.
"""

from __future__ import annotations

import csv
import io
from typing import List

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..models.call_log import CallLog, CallStatus
from ..services.call_manager import enqueue_calls, execute_call_sequence
from ..utils import (
    limit_numbers,
    parse_numbers_from_csv,
    parse_numbers_from_text,
    unique_preserve_order,
    validate_number,
)


router = APIRouter(tags=["Calls"])
templates = Jinja2Templates(directory="app/templates")

DEFAULT_MESSAGE = "Hello from Autodialer test system."


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Render the home page with forms for bulk upload and AI commands."""

    return await _render_index(request)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render a comprehensive dashboard with call history details."""

    return await _render_dashboard(request)


@router.post("/calls/upload", response_class=HTMLResponse)
async def upload_numbers(
    request: Request,
    background_tasks: BackgroundTasks,
    numbers_text: str = Form(""),
    numbers_file: UploadFile | None = File(None),
) -> HTMLResponse:
    """
    Accept phone numbers via text area or CSV upload and queue them for calling.
    """

    numbers = parse_numbers_from_text(numbers_text) if numbers_text else []

    if numbers_file is not None:
        content = await numbers_file.read()
        numbers.extend(parse_numbers_from_csv(content))

    numbers = unique_preserve_order(numbers)
    numbers = limit_numbers(numbers)

    validations = [validate_number(number) for number in numbers]
    valid_numbers = [item.number for item in validations if item.is_valid]
    warnings = [item.reason for item in validations if not item.is_valid and item.reason]

    if not valid_numbers:
        return await _render_index(
            request,
            alert="No Twilio test numbers were accepted. Please submit numbers beginning with +1500.",
            warnings=warnings,
        )

    async_session = request.app.state.async_session
    twilio_service = request.app.state.twilio_service

    tasks = await enqueue_calls(valid_numbers, DEFAULT_MESSAGE, async_session)

    background_tasks.add_task(
        execute_call_sequence,
        tasks,
        async_session,
        twilio_service,
    )

    success_message = f"Queued {len(tasks)} call(s). Calls will execute in the background."

    return await _render_index(
        request,
        alert=success_message,
        warnings=warnings,
    )


@router.get("/calls/export", response_class=StreamingResponse)
async def export_logs(request: Request) -> StreamingResponse:
    """Download call logs as a CSV file."""

    session_factory: async_sessionmaker[AsyncSession] = request.app.state.async_session
    async with session_factory() as session:
        logs_stmt = select(CallLog).order_by(CallLog.created_at.desc())
        logs_result = await session.execute(logs_stmt)
        call_logs = logs_result.scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "number", "status", "duration", "message", "error", "call_sid", "created_at"])
    for log in call_logs:
        writer.writerow(
            [
                log.id,
                log.number,
                log.status.value if isinstance(log.status, CallStatus) else log.status,
                log.duration or "",
                (log.message or "").replace("\n", " "),
                (log.error or "").replace("\n", " "),
                log.call_sid or "",
                log.created_at.isoformat(),
            ]
        )

    buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="call_logs.csv"'}
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers=headers)


async def _render_index(
    request: Request,
    *,
    alert: str | None = None,
    warnings: List[str] | None = None,
) -> HTMLResponse:
    context = await build_dashboard_context(request, limit=25)
    context.update({"alert": alert, "warnings": warnings or []})
    return templates.TemplateResponse("index.html", context)


async def _render_dashboard(request: Request) -> HTMLResponse:
    context = await build_dashboard_context(request, limit=100)
    return templates.TemplateResponse("dashboard.html", context)


async def build_dashboard_context(request: Request, *, limit: int) -> dict:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.async_session
    async with session_factory() as session:
        logs_stmt = (
            select(CallLog).order_by(CallLog.created_at.desc()).limit(limit)
        )
        logs_result = await session.execute(logs_stmt)
        call_logs = logs_result.scalars().all()

        stats_stmt = (
            select(CallLog.status, func.count().label("count"))
            .group_by(CallLog.status)
        )
        stats_result = await session.execute(stats_stmt)
        stats_map = {status.value: count for status, count in stats_result.all()}

    success_count = stats_map.get(CallStatus.SUCCESS.value, 0)
    failed_count = stats_map.get(CallStatus.FAILED.value, 0)
    skipped_count = stats_map.get(CallStatus.SKIPPED.value, 0)
    queued_count = stats_map.get(CallStatus.QUEUED.value, 0)
    in_progress_count = stats_map.get(CallStatus.IN_PROGRESS.value, 0)

    return {
        "request": request,
        "call_logs": call_logs,
        "stats": {
            "success": success_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "queued": queued_count,
            "in_progress": in_progress_count,
        },
        "total_calls": sum(stats_map.values()),
    }

