"""
Utility helpers for parsing and validating phone numbers within Autodialer.

The helpers in this module are intentionally lightweight so that they can be
reused across both API routes and background services.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence


INDIAN_NUMBER_REGEX = re.compile(r"^(?:\+91|0)?([6-9]\d{9})$")
TWILIO_TEST_PREFIX = "+1500"
MAX_BULK_UPLOAD = 100
ANSI_ESCAPE_REGEX = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


@dataclass(slots=True)
class NumberValidationResult:
    """Represents the outcome of validating a phone number."""

    number: str
    is_valid: bool
    reason: str | None = None


def normalize_number(raw: str) -> str:
    """
    Normalize a phone number by stripping whitespace and standardizing prefixes.

    Args:
        raw: User supplied phone number string.

    Returns:
        The sanitized number string without whitespace or hyphen separators.
    """

    number = re.sub(r"[^\d\+]", "", raw.strip())
    if number.startswith("00"):
        number = "+" + number[2:]
    if number.startswith("0") and not number.startswith("+"):
        number = number[1:]
    if number.startswith("91") and len(number) == 12:
        number = f"+{number}"
    if number.startswith("+") and len(number) > 1:
        return number
    if len(number) == 10:
        return f"+91{number}"
    return number


def validate_number(number: str) -> NumberValidationResult:
    """
    Validate that the number complies with Indian numbering or Twilio test rules.

    Args:
        number: Phone number string (expected in E.164 format).

    Returns:
        A :class:`NumberValidationResult` describing the validation outcome.
    """

    if number.startswith(TWILIO_TEST_PREFIX):
        return NumberValidationResult(number=number, is_valid=True)

    match = INDIAN_NUMBER_REGEX.match(number)
    if match:
        canonical = f"+91{match.group(1)}"
        return NumberValidationResult(
            number=canonical,
            is_valid=False,
            reason=(
                "Indian numbers detected. Autodialer only places calls to Twilio test "
                "numbers (starting with +1500...) for safety."
            ),
        )

    return NumberValidationResult(
        number=number,
        is_valid=False,
        reason="Invalid phone number format. Provide Twilio test numbers e.g. +15005550006.",
    )


def parse_numbers_from_text(value: str) -> List[str]:
    """
    Parse a block of text into candidate phone numbers.

    Args:
        value: Raw text supplied through the textarea input.

    Returns:
        A list of normalized strings extracted from the text block.
    """

    candidates = re.split(r"[,\n; ]+", value.strip())
    normalized = [normalize_number(token) for token in candidates if token.strip()]
    return [n for n in normalized if n]


def parse_numbers_from_csv(content: bytes) -> List[str]:
    """
    Parse CSV content for phone numbers (first column in each row).

    Args:
        content: Raw bytes read from the uploaded CSV file.

    Returns:
        A list of normalized numbers discovered in the CSV.
    """

    if not content:
        return []

    decoded = content.decode("utf-8", errors="ignore")
    reader = csv.reader(io.StringIO(decoded))
    numbers: List[str] = []

    for row in reader:
        if not row:
            continue
        numbers.append(normalize_number(row[0]))

    return [n for n in numbers if n]


def unique_preserve_order(numbers: Sequence[str]) -> List[str]:
    """
    Deduplicate a sequence of numbers while preserving insertion order.

    Args:
        numbers: An iterable sequence of number strings.

    Returns:
        A list of unique numbers in their original order.
    """

    seen = set()
    unique: List[str] = []
    for number in numbers:
        if number and number not in seen:
            unique.append(number)
            seen.add(number)
    return unique


def limit_numbers(numbers: Iterable[str], limit: int = MAX_BULK_UPLOAD) -> List[str]:
    """
    Ensure the number of phone numbers does not exceed the configured limit.

    Args:
        numbers: Iterable containing sanitized number strings.
        limit: Maximum numbers allowed (defaults to 100).

    Returns:
        A truncated list of numbers capped at ``limit`` entries.
    """

    return list(numbers)[:limit]


def strip_ansi(value: Optional[str]) -> Optional[str]:
    """
    Remove ANSI escape sequences from a string.

    Args:
        value: String that may contain terminal colour codes.

    Returns:
        Cleaned string without ANSI sequences, or ``None`` if the input was ``None``.
    """

    if not value:
        return value
    return ANSI_ESCAPE_REGEX.sub("", value)


