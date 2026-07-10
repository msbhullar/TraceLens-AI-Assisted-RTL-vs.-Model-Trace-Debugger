"""
Parses raw RTL/TLM log files (per docs/log_format.md) into lists of
TraceEvent objects.

Format per line:
    <timestamp_ns> | <txn_id> | <event_type> | <field=value> [field=value ...]
"""

from pathlib import Path
from typing import List

from app.models import EventType, TraceEvent, TraceSource


class LogParseError(ValueError):
    """Raised when a log line doesn't conform to the expected schema."""


def _parse_fields(field_str: str) -> dict:
    fields = {}
    for chunk in field_str.strip().split():
        if "=" not in chunk:
            raise LogParseError(f"Malformed field token: {chunk!r}")
        key, value = chunk.split("=", 1)
        fields[key] = value
    return fields


def parse_line(line: str, source: TraceSource) -> TraceEvent:
    """Parse a single log line into a TraceEvent."""
    stripped = line.strip()
    parts = [p.strip() for p in stripped.split("|")]
    if len(parts) != 4:
        raise LogParseError(f"Expected 4 pipe-delimited fields, got {len(parts)}: {line!r}")

    ts_str, txn_id, event_type_str, field_str = parts

    try:
        timestamp_ns = int(ts_str)
    except ValueError as e:
        raise LogParseError(f"Invalid timestamp {ts_str!r} in line: {line!r}") from e

    try:
        event_type = EventType(event_type_str)
    except ValueError as e:
        raise LogParseError(f"Unknown event_type {event_type_str!r} in line: {line!r}") from e

    fields = _parse_fields(field_str)

    return TraceEvent(
        timestamp_ns=timestamp_ns,
        txn_id=txn_id,
        event_type=event_type,
        source=source,
        addr=fields.get("addr"),
        data=fields.get("data"),
        mode=fields.get("mode"),
        state=fields.get("state"),
        note=fields.get("note"),
        raw_line=stripped,
    )


def parse_log_text(text: str, source: TraceSource) -> List[TraceEvent]:
    """Parse full log text (multiple lines) into a list of TraceEvents.

    Blank lines and lines starting with '#' are skipped.
    """
    events: List[TraceEvent] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            events.append(parse_line(line, source))
        except LogParseError as e:
            raise LogParseError(f"Line {line_no}: {e}") from e
    return events


def parse_log_file(path: str | Path, source: TraceSource) -> List[TraceEvent]:
    """Parse a log file from disk into a list of TraceEvents."""
    text = Path(path).read_text()
    return parse_log_text(text, source)
