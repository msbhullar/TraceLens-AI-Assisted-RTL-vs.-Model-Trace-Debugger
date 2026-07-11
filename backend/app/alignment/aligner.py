"""
Deterministic alignment engine: matches RTL transactions to their TLM
counterparts by txn_id, falling back to (event_type, addr) matching when
txn_id sequences diverge (e.g. a missing or extra transaction threw off
simple 1:1 pairing).

ANNOTATION events are excluded from alignment (they carry no transaction
identity to match on) but are returned separately so callers can still use
them for context.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from app.models import EventType, TraceEvent


@dataclass
class AlignedPair:
    """One matched RTL <-> TLM transaction."""

    rtl_event: TraceEvent
    tlm_event: TraceEvent
    rtl_index: int  # position in the (non-annotation) RTL sequence
    tlm_index: int  # position in the (non-annotation) TLM sequence
    matched_by_fallback: bool = False  # True if matched via (event_type, addr), not txn_id


@dataclass
class AlignmentResult:
    aligned: List[AlignedPair] = field(default_factory=list)
    missing_in_tlm: List[TraceEvent] = field(default_factory=list)  # in RTL only
    extra_in_tlm: List[TraceEvent] = field(default_factory=list)  # in TLM only
    rtl_annotations: List[TraceEvent] = field(default_factory=list)
    tlm_annotations: List[TraceEvent] = field(default_factory=list)


def _split_annotations(events: List[TraceEvent]) -> tuple[List[TraceEvent], List[TraceEvent]]:
    """Returns (non_annotation_events, annotation_events), preserving order."""
    non_annotations = [e for e in events if e.event_type != EventType.ANNOTATION]
    annotations = [e for e in events if e.event_type == EventType.ANNOTATION]
    return non_annotations, annotations


def align_events(rtl_events: List[TraceEvent], tlm_events: List[TraceEvent]) -> AlignmentResult:
    """
    Align RTL and TLM event sequences into matched pairs.

    Returns an AlignmentResult with matched pairs plus whatever couldn't be
    matched on either side.
    """
    rtl_txns, rtl_annotations = _split_annotations(rtl_events)
    tlm_txns, tlm_annotations = _split_annotations(tlm_events)

    # Index TLM events by txn_id for O(1) primary-pass lookup.
    tlm_by_id: dict[str, tuple[int, TraceEvent]] = {}
    for idx, ev in enumerate(tlm_txns):
        tlm_by_id.setdefault(ev.txn_id, (idx, ev))

    aligned: List[AlignedPair] = []
    matched_tlm_indices: set[int] = set()
    unmatched_rtl: List[tuple[int, TraceEvent]] = []

    # --- Primary pass: match by txn_id ---
    for rtl_idx, rtl_ev in enumerate(rtl_txns):
        hit = tlm_by_id.get(rtl_ev.txn_id)
        if hit is not None and hit[0] not in matched_tlm_indices:
            tlm_idx, tlm_ev = hit
            aligned.append(AlignedPair(rtl_ev, tlm_ev, rtl_idx, tlm_idx, matched_by_fallback=False))
            matched_tlm_indices.add(tlm_idx)
        else:
            unmatched_rtl.append((rtl_idx, rtl_ev))

    unmatched_tlm = [
        (idx, ev) for idx, ev in enumerate(tlm_txns) if idx not in matched_tlm_indices
    ]

    # --- Fallback pass: match remaining events by (event_type, addr), in order ---
    still_unmatched_rtl: List[tuple[int, TraceEvent]] = []
    consumed_tlm_positions: set[int] = set()

    for rtl_idx, rtl_ev in unmatched_rtl:
        match_pos: Optional[int] = None
        for pos, (tlm_idx, tlm_ev) in enumerate(unmatched_tlm):
            if pos in consumed_tlm_positions:
                continue
            if tlm_ev.event_type == rtl_ev.event_type and tlm_ev.addr == rtl_ev.addr:
                match_pos = pos
                break

        if match_pos is not None:
            tlm_idx, tlm_ev = unmatched_tlm[match_pos]
            aligned.append(AlignedPair(rtl_ev, tlm_ev, rtl_idx, tlm_idx, matched_by_fallback=True))
            consumed_tlm_positions.add(match_pos)
        else:
            still_unmatched_rtl.append((rtl_idx, rtl_ev))

    remaining_tlm = [
        ev for pos, (idx, ev) in enumerate(unmatched_tlm) if pos not in consumed_tlm_positions
    ]

    # Keep aligned pairs in RTL order for readability downstream.
    aligned.sort(key=lambda p: p.rtl_index)

    return AlignmentResult(
        aligned=aligned,
        missing_in_tlm=[ev for _, ev in still_unmatched_rtl],
        extra_in_tlm=remaining_tlm,
        rtl_annotations=rtl_annotations,
        tlm_annotations=tlm_annotations,
    )
