"""
SQLAlchemy model definitions for the Autodialer application.

This module declares the database schema for persisting call metadata,
including status tracking and timestamps for each automated call attempt.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SqlEnum, Integer, String, Text
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class CallStatus(str, Enum):
    """Enumerated status values for call lifecycle tracking."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class CallLog(Base):
    """
    ORM model mapping for the ``calls`` table.

    Attributes:
        id: Primary key identifier for the call log entry.
        number: Target phone number for the call attempt (E.164 format).
        message: Voice message delivered via the Twilio call.
        status: Current state of the call lifecycle (enum).
        duration: Reported duration (in seconds) returned by Twilio.
        error: Optional error detail when a call fails or is skipped.
        call_sid: Twilio Call SID for traceability inside the Twilio console.
        created_at: Timestamp when the log entry was created.
        updated_at: Timestamp for the most recent status update.
    """

    __tablename__ = "calls"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String(32), nullable=False)
    message = Column(Text, nullable=True)
    status = Column(SqlEnum(CallStatus), default=CallStatus.QUEUED, nullable=False)
    duration = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    call_sid = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def mark(
        self,
        status: CallStatus,
        *,
        duration: int | None = None,
        error: str | None = None,
        call_sid: str | None = None,
    ) -> None:
        """
        Update the log entry with the provided status metadata.

        Args:
            status: New lifecycle status for the call.
            duration: Optional call duration in seconds.
            error: Optional error message if the call failed or was skipped.
            call_sid: Optional Twilio Call SID for reference.
        """

        self.status = status
        if duration is not None:
            self.duration = duration
        if error is not None:
            self.error = error
        if call_sid is not None:
            self.call_sid = call_sid
        self.updated_at = datetime.utcnow()


