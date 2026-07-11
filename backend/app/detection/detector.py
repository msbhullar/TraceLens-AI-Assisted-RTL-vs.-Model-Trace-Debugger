"""
Mismatch detection engine.

Takes an AlignmentResult (from app.alignment.aligner) and classifies every
divergence into one of the 7 mismatch categories from docs/log_format.md.
"""

from dataclasses import dataclass
from typing import List

from app.alignment.aligner import AlignedPair, AlignmentResult
from app.parser.synthetic_generator import MismatchType

DEFAULT_TIMING_THRESHOLD_NS = 100


@dataclass
class Finding:
    """One detected mismatch, ready to be handed to the LLM explanation layer."""

    mismatch_type: MismatchType
    txn_ids: List[str]
    description: str


def _detect_pair_mismatches(pair: AlignedPair, timing_threshold_ns: int) -> List[Finding]:
    """Compare one aligned RTL/TLM pair and return every mismatch found."""
    findings: List[Finding] = []
    rtl, tlm = pair.rtl_event, pair.tlm_event

    if rtl.addr != tlm.addr:
        findings.append(
            Finding(
                MismatchType.ADDRESS_MISMATCH,
                [rtl.txn_id],
                f"{rtl.txn_id}: addr differs -- RTL={rtl.addr}, TLM={tlm.addr}",
            )
        )
    elif rtl.data != tlm.data:
        findings.append(
            Finding(
                MismatchType.DATA_MISMATCH,
                [rtl.txn_id],
                f"{rtl.txn_id}: data differs -- RTL={rtl.data}, TLM={tlm.data}",
            )
        )

    if rtl.state != tlm.state:
        findings.append(
            Finding(
                MismatchType.STATE_MISMATCH,
                [rtl.txn_id],
                f"{rtl.txn_id}: state differs -- RTL={rtl.state}, TLM={tlm.state}",
            )
        )

    ts_delta = abs(rtl.timestamp_ns - tlm.timestamp_ns)
    if ts_delta > timing_threshold_ns:
        findings.append(
            Finding(
                MismatchType.TIMING_MISMATCH,
                [rtl.txn_id],
                f"{rtl.txn_id}: timestamp differs by {ts_delta}ns "
                f"(RTL={rtl.timestamp_ns}, TLM={tlm.timestamp_ns})",
            )
        )

    return findings


def _detect_ordering_mismatches(result: AlignmentResult) -> List[Finding]:
    """
    Compare relative order across aligned pairs. If TLM's transaction order
    doesn't match RTL's, flag the out-of-place pair.
    """
    findings: List[Finding] = []
    sorted_pairs = sorted(result.aligned, key=lambda p: p.rtl_index)

    prev_tlm_index = -1
    prev_txn_id = None
    for pair in sorted_pairs:
        if pair.tlm_index < prev_tlm_index:
            findings.append(
                Finding(
                    MismatchType.ORDERING_MISMATCH,
                    [prev_txn_id, pair.rtl_event.txn_id],
                    f"{pair.rtl_event.txn_id} appears out of order in TLM relative to "
                    f"{prev_txn_id} (RTL order says {prev_txn_id} should come first)",
                )
            )
        else:
            prev_tlm_index = pair.tlm_index
        prev_txn_id = pair.rtl_event.txn_id

    return findings


def detect_mismatches(
    result: AlignmentResult, timing_threshold_ns: int = DEFAULT_TIMING_THRESHOLD_NS
) -> List[Finding]:
    """
    Classify every divergence in an AlignmentResult into the 7 mismatch
    categories. Returns a flat list of Findings.
    """
    findings: List[Finding] = []

    for ev in result.missing_in_tlm:
        findings.append(
            Finding(
                MismatchType.MISSING_TRANSACTION,
                [ev.txn_id],
                f"{ev.txn_id} present in RTL but missing from TLM",
            )
        )

    for ev in result.extra_in_tlm:
        findings.append(
            Finding(
                MismatchType.EXTRA_TRANSACTION,
                [ev.txn_id],
                f"{ev.txn_id} present in TLM but not in RTL",
            )
        )

    for pair in result.aligned:
        findings.extend(_detect_pair_mismatches(pair, timing_threshold_ns))

    findings.extend(_detect_ordering_mismatches(result))

    return findings
