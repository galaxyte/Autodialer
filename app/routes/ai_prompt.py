"""
Routes dedicated to handling natural-language AI commands for Autodialer.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..services.call_manager import enqueue_calls, execute_call_sequence
from ..services.ai_service import PromptParseResult
from ..utils import validate_number
from .calls import build_dashboard_context


router = APIRouter(prefix="/ai", tags=["AI"])
templates = Jinja2Templates(directory="app/templates")


@router.post("/prompt", response_class=HTMLResponse)
async def handle_prompt(
    request: Request,
    background_tasks: BackgroundTasks,
    prompt: str = Form(...),
) -> HTMLResponse:
    """
    Parse the AI instruction, validate the extracted number, and schedule a call.
    """

    ai_service = request.app.state.ai_service
    async_session = request.app.state.async_session
    twilio_service = request.app.state.twilio_service

    try:
        parsed = await ai_service.parse_prompt(prompt)
    except Exception as exc:  # noqa: BLE001
        return await _render_with_context(
            request,
            alert="Unable to process AI prompt.",
            warnings=[f"Error: {exc}"],
        )

    feedback = _validate_ai_result(parsed)
    if feedback.warnings:
        return await _render_with_context(
            request,
            alert="Prompt processed with warnings.",
            warnings=feedback.warnings,
        )

    tasks = await enqueue_calls(
        [feedback.number],
        feedback.message,
        async_session,
    )

    background_tasks.add_task(
        execute_call_sequence,
        tasks,
        async_session,
        twilio_service,
    )

    return await _render_with_context(
        request,
        alert=f"AI scheduled a call to {feedback.number}.",
        warnings=[],
    )


async def _render_with_context(
    request: Request,
    *,
    alert: str | None,
    warnings: list[str],
) -> HTMLResponse:
    context = await build_dashboard_context(request, limit=25)
    context.update({"alert": alert, "warnings": warnings})
    return templates.TemplateResponse("index.html", context)


class AIValidationFeedback:
    """Helper structure describing the result of validating AI output."""

    def __init__(
        self,
        *,
        number: str | None,
        message: str,
        warnings: list[str],
    ) -> None:
        self.number = number
        self.message = message
        self.warnings = warnings


def _validate_ai_result(parsed: PromptParseResult) -> AIValidationFeedback:
    warnings: list[str] = []
    number = parsed.number

    if not number:
        warnings.append(
            "No phone number could be extracted. Add a valid Twilio test number in your prompt."
        )
        return AIValidationFeedback(number=None, message=parsed.message or "", warnings=warnings)

    validation = validate_number(number)
    if not validation.is_valid:
        warn = validation.reason or "Unsupported number provided."
        warnings.append(warn)
        return AIValidationFeedback(number=None, message=parsed.message or "", warnings=warnings)

    return AIValidationFeedback(
        number=validation.number,
        message=parsed.message or "Hello from Autodialer test system.",
        warnings=[],
    )

