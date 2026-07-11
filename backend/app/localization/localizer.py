"""
First-divergence localization.

Takes the Findings from detection (app.detection.detector) plus the
AlignmentResult they came from, and determines the earliest point in
simulated time where RTL and TLM actually diverge -- turning "here are
N mismatches somewhere in this log" into "here is the single event where
things first went wrong."
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.alignment.aligner import AlignmentResult
from app.detection.detector import Finding
from app.models import TraceEvent


@dataclass
class TimestampedFinding:
    """A Finding annotated with the simulated timestamp it occurred at."""

    finding: Finding
    timestamp_ns: int


@dataclass
class LocalizationResult:
    first_divergence: Optional[TimestampedFinding]
    timeline: List[TimestampedFinding]  # all findings, sorted earliest-first


def _build_timestamp_lookup(result: AlignmentResult) -> Dict[str, int]:
    """
    Maps txn_id -> timestamp_ns, preferring the RTL timestamp (ground truth)
    wherever a transaction exists in RTL. Falls back to the TLM timestamp for
    transactions that only exist in TLM (EXTRA_TRANSACTION findings).
    """
    lookup: Dict[str, int] = {}

    # TLM-only timestamps first (lower priority) ...
    for ev in result.extra_in_tlm:
        lookup[ev.txn_id] = ev.timestamp_ns
    for pair in result.aligned:
        lookup[pair.tlm_event.txn_id] = pair.tlm_event.timestamp_ns

    # ... then RTL timestamps overwrite them (higher priority: RTL is ground truth).
    for ev in result.missing_in_tlm:
        lookup[ev.txn_id] = ev.timestamp_ns
    for pair in result.aligned:
        lookup[pair.rtl_event.txn_id] = pair.rtl_event.timestamp_ns

    return lookup


def localize(result: AlignmentResult, findings: List[Finding]) -> LocalizationResult:
    """
    Sort findings by when they occurred in simulated time and identify the
    first divergence.
    """
    if not findings:
        return LocalizationResult(first_divergence=None, timeline=[])

    timestamp_lookup = _build_timestamp_lookup(result)

    timestamped: List[TimestampedFinding] = []
    for f in findings:
        # A finding can involve multiple txn_ids (e.g. ORDERING_MISMATCH);
        # use the earliest timestamp among them as the finding's occurrence time.
        candidate_timestamps = [
            timestamp_lookup[txn_id] for txn_id in f.txn_ids if txn_id in timestamp_lookup
        ]
        if not candidate_timestamps:
            # Shouldn't normally happen, but don't silently drop a finding --
            # push it to the end rather than crash.
            timestamped.append(TimestampedFinding(f, timestamp_ns=float("inf")))
            continue
        timestamped.append(TimestampedFinding(f, timestamp_ns=min(candidate_timestamps)))

    timeline = sorted(timestamped, key=lambda tf: tf.timestamp_ns)

    return LocalizationResult(first_divergence=timeline[0], timeline=timeline)
