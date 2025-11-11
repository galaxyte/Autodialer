"""
Service integration with OpenAI for parsing natural-language call commands.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from ..utils import normalize_number


load_dotenv()


PROMPT_TEMPLATE = (
    "Extract the destination phone number and the message to deliver via a phone call. "
    "Return JSON with keys 'number' and 'message'. Only include digits and '+' in the number. "
    "If the number is missing, leave it empty. Keep the message short and friendly."
)


@dataclass(slots=True)
class PromptParseResult:
    """Represents the output of parsing a natural language request."""

    number: Optional[str]
    message: Optional[str]
    raw_response: str


class AIService:
    """
    Wrapper on top of OpenAI's API that extracts instructions for automated calls.
    """

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OpenAI API key missing. Set OPENAI_API_KEY in your environment."
            )
        self._client = OpenAI(api_key=api_key)

    async def parse_prompt(self, prompt: str) -> PromptParseResult:
        """
        Interpret a user's natural language command.

        Args:
            prompt: Original text provided by the user.

        Returns:
            A :class:`PromptParseResult` with structured data extracted from the prompt.
        """

        structured = await asyncio.to_thread(self._invoke_model, prompt)

        number = structured.get("number")
        message = structured.get("message") or "Hello from Autodialer test system."

        if number:
            number = normalize_number(number)

        if not number:
            fallback = self._fallback_number(prompt)
            number = fallback

        return PromptParseResult(
            number=number,
            message=message.strip(),
            raw_response=json.dumps(structured),
        )

    def _invoke_model(self, prompt: str) -> dict[str, str]:
        instruction = (
            f"{PROMPT_TEMPLATE} Respond with JSON only. "
            "If you cannot find a number, set it to an empty string."
        )
        response = self._client.responses.create(
            model="gpt-4o-mini",
            input=f"{instruction}\n\nPrompt:\n{prompt}\n\nJSON:",
        )

        content = getattr(response, "output_text", None)
        if not content and response.output:
            content = response.output[0].content[0].text
        if not content:
            content = "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _fallback_number(prompt: str) -> Optional[str]:
        digits = re.findall(r"\+?\d{7,15}", prompt)
        if digits:
            return normalize_number(digits[0])
        return None

