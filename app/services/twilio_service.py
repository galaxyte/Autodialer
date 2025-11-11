"""
Abstractions for interacting with Twilio's Voice API in a test-friendly manner.

The TwilioService centralises creation of the API client, enforces that only
approved Twilio test numbers are dialled, and exposes async-compatible helpers
for placing calls without blocking the main event loop.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from ..utils import TWILIO_TEST_PREFIX, strip_ansi


load_dotenv()


@dataclass(slots=True)
class CallResult:
    """Container describing the result of attempting a Twilio call."""

    success: bool
    sid: Optional[str] = None
    duration: Optional[int] = None
    error: Optional[str] = None


class TwilioService:
    """
    Service wrapper around Twilio's REST API with safety checks for test mode.
    """

    def __init__(self) -> None:
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.getenv("TWILIO_FROM_NUMBER", "")

        if not all([self.account_sid, self.auth_token, self.from_number]):
            raise RuntimeError(
                "Twilio environment variables are missing. Ensure TWILIO_ACCOUNT_SID, "
                "TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER are configured."
            )

        self._client = Client(self.account_sid, self.auth_token)

    @staticmethod
    def ensure_test_mode(number: str) -> None:
        """
        Guard against placing real calls by enforcing Twilio's test prefix.

        Raises:
            ValueError: If the number is not within the Twilio test range.
        """

        if not number.startswith(TWILIO_TEST_PREFIX):
            raise ValueError(
                "Only Twilio test numbers are permitted. Use numbers beginning with +1500."
            )

    async def place_call(self, to_number: str, message: str) -> CallResult:
        """
        Initiate a Twilio voice call delivered with the supplied message.

        Args:
            to_number: Destination phone number (must be Twilio test number).
            message: Text that will be synthesised to speech for the call.

        Returns:
            A :class:`CallResult` describing success or failure.
        """

        self.ensure_test_mode(to_number)

        twiml = f"<Response><Say voice='Polly.Joanna'>{message}</Say></Response>"

        try:
            call = await asyncio.to_thread(
                self._client.calls.create,
                twiml=twiml,
                to=to_number,
                from_=self.from_number,
            )
            return CallResult(success=True, sid=call.sid, duration=call.duration)
        except TwilioRestException as exc:
            return CallResult(success=False, error=strip_ansi(str(exc)))
        except Exception as exc:  # noqa: BLE001 - propagate as failure detail
            return CallResult(success=False, error=strip_ansi(f"Unexpected error: {exc}"))

