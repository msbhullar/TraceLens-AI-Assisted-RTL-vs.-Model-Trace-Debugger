"""
Pydantic models for TraceLens trace events.

These represent a single parsed line from an RTL or TLM log, per the schema
in docs/log_format.md.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventType(str, Enum):
    REG_READ = "REG_READ"
    REG_WRITE = "REG_WRITE"
    BUS_ACCESS = "BUS_ACCESS"
    PKT_TX = "PKT_TX"
    PKT_RX = "PKT_RX"
    ANNOTATION = "ANNOTATION"


class BusMode(str, Enum):
    READ = "READ"
    WRITE = "WRITE"


class ProtocolState(str, Enum):
    IDLE = "IDLE"
    FILTER_ACTIVE = "FILTER_ACTIVE"
    FILTER_DONE = "FILTER_DONE"
    ERROR = "ERROR"


class TraceSource(str, Enum):
    RTL = "RTL"
    TLM = "TLM"


class TraceEvent(BaseModel):
    """A single event parsed from an RTL or TLM log line."""

    timestamp_ns: int = Field(..., ge=0)
    txn_id: str
    event_type: EventType
    source: TraceSource

    addr: Optional[str] = None
    data: Optional[str] = None
    mode: Optional[BusMode] = None
    state: Optional[ProtocolState] = None
    note: Optional[str] = None

    raw_line: Optional[str] = Field(
        default=None, description="Original log line, kept for debug summaries"
    )

    @field_validator("addr", "data")
    @classmethod
    def _lowercase_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.lower()

    def is_annotation(self) -> bool:
        return self.event_type == EventType.ANNOTATION

    model_config = ConfigDict(use_enum_values=True, frozen=True)
