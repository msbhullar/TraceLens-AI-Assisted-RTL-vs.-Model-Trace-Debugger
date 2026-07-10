"""
Synthetic RTL/TLM log generator.

Generates a "ground truth" RTL log for a CAN XL / MACsec-style test scenario
(register access, bus transactions, packet TX/RX, annotations), then produces
a matching TLM log. Optionally injects one of the 7 mismatch categories into
the TLM log at a controlled point, returning ground-truth labels alongside
the generated logs so this doubles as an eval harness.

Usage:
    from app.parser.synthetic_generator import generate_pair, MismatchType

    rtl_text, tlm_text, injected = generate_pair(
        n_transactions=40, seed=1, inject=MismatchType.DATA_MISMATCH
    )
"""

import random
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

STATES = ["IDLE", "FILTER_ACTIVE", "FILTER_DONE", "ERROR"]
ANNOTATIONS = ["FILTER_START", "FILTER_END", "HEADER_ERROR", "CRC_ERROR"]


class MismatchType(str, Enum):
    DATA_MISMATCH = "DATA_MISMATCH"
    ADDRESS_MISMATCH = "ADDRESS_MISMATCH"
    TIMING_MISMATCH = "TIMING_MISMATCH"
    STATE_MISMATCH = "STATE_MISMATCH"
    MISSING_TRANSACTION = "MISSING_TRANSACTION"
    EXTRA_TRANSACTION = "EXTRA_TRANSACTION"
    ORDERING_MISMATCH = "ORDERING_MISMATCH"


@dataclass
class RawEvent:
    timestamp_ns: int
    txn_id: str
    event_type: str
    fields: dict

    def to_line(self) -> str:
        field_str = " ".join(f"{k}={v}" for k, v in self.fields.items())
        return f"{self.timestamp_ns} | {self.txn_id} | {self.event_type} | {field_str}"


@dataclass
class InjectedMismatch:
    mismatch_type: MismatchType
    txn_id: str
    description: str


def _rand_hex(rng: random.Random, nbits: int = 32) -> str:
    return f"0x{rng.getrandbits(nbits):0{nbits // 4}X}"


def _gen_base_events(n_transactions: int, rng: random.Random) -> List[RawEvent]:
    """Generate the RTL ground-truth event sequence."""
    events: List[RawEvent] = []
    ts = 1000
    state = "IDLE"
    annotation_counter = 0

    event_type_cycle = ["REG_WRITE", "REG_READ", "BUS_ACCESS", "PKT_TX", "PKT_RX"]

    for i in range(n_transactions):
        ts += rng.randint(2, 10)
        etype = event_type_cycle[i % len(event_type_cycle)]
        txn_id = f"TXN{i + 1:04d}"

        if etype in ("REG_WRITE", "REG_READ"):
            fields = {"addr": _rand_hex(rng, 16), "data": _rand_hex(rng, 32)}
        elif etype == "BUS_ACCESS":
            mode = "READ" if i % 2 == 0 else "WRITE"
            fields = {"addr": _rand_hex(rng, 16), "mode": mode, "data": _rand_hex(rng, 32)}
        else:  # PKT_TX / PKT_RX
            if i % 7 == 0:
                state = rng.choice(STATES)
            fields = {"data": _rand_hex(rng, 32), "state": state}

        events.append(RawEvent(ts, txn_id, etype, fields))

        # Occasionally drop in a manual annotation (not part of alignment)
        if i % 9 == 4:
            annotation_counter += 1
            ts += 1
            events.append(
                RawEvent(
                    ts,
                    "TXN0000",
                    "ANNOTATION",
                    {"note": rng.choice(ANNOTATIONS)},
                )
            )

    return events


def _clone_events(events: List[RawEvent]) -> List[RawEvent]:
    return [RawEvent(e.timestamp_ns, e.txn_id, e.event_type, dict(e.fields)) for e in events]


def _inject_mismatch(
    tlm_events: List[RawEvent], mismatch: MismatchType, rng: random.Random
) -> Tuple[List[RawEvent], InjectedMismatch]:
    """Mutate a copy of the TLM events to introduce exactly one mismatch."""
    non_annotation_idx = [i for i, e in enumerate(tlm_events) if e.event_type != "ANNOTATION"]
    # Pick a target somewhere in the middle third, so there's clean context
    # before and after the injected divergence (useful for localization testing).
    lo = len(non_annotation_idx) // 3
    hi = 2 * len(non_annotation_idx) // 3
    target_pos = rng.choice(non_annotation_idx[lo:hi])
    target = tlm_events[target_pos]

    if mismatch == MismatchType.DATA_MISMATCH:
        if "data" not in target.fields:
            target.fields["data"] = _rand_hex(rng, 32)
        old = target.fields["data"]
        new = _rand_hex(rng, 32)
        target.fields["data"] = new
        desc = f"data changed from {old} to {new} at {target.txn_id}"

    elif mismatch == MismatchType.ADDRESS_MISMATCH:
        if "addr" not in target.fields:
            target.fields["addr"] = _rand_hex(rng, 16)
        old = target.fields["addr"]
        new = _rand_hex(rng, 16)
        target.fields["addr"] = new
        desc = f"addr changed from {old} to {new} at {target.txn_id}"

    elif mismatch == MismatchType.TIMING_MISMATCH:
        old = target.timestamp_ns
        target.timestamp_ns += rng.randint(500, 1000)
        desc = f"timestamp shifted from {old} to {target.timestamp_ns} at {target.txn_id}"

    elif mismatch == MismatchType.STATE_MISMATCH:
        if "state" not in target.fields:
            target.fields["state"] = rng.choice(STATES)
        old = target.fields["state"]
        choices = [s for s in STATES if s != old]
        target.fields["state"] = rng.choice(choices)
        desc = f"state changed from {old} to {target.fields['state']} at {target.txn_id}"

    elif mismatch == MismatchType.MISSING_TRANSACTION:
        desc = f"{target.txn_id} removed from TLM (present in RTL only)"
        tlm_events.pop(target_pos)

    elif mismatch == MismatchType.EXTRA_TRANSACTION:
        extra = RawEvent(
            target.timestamp_ns + 1,
            f"EXTRA{rng.randint(1000, 9999)}",
            "BUS_ACCESS",
            {"addr": _rand_hex(rng, 16), "mode": "READ", "data": _rand_hex(rng, 32)},
        )
        tlm_events.insert(target_pos + 1, extra)
        desc = f"{extra.txn_id} inserted into TLM (not present in RTL)"
        target = extra  # for labeling purposes

    elif mismatch == MismatchType.ORDERING_MISMATCH:
        # Swap target with the next non-annotation event
        later_candidates = [i for i in non_annotation_idx if i > target_pos]
        if not later_candidates:
            desc = "ordering swap skipped (no later event available)"
        else:
            swap_pos = later_candidates[0]
            tlm_events[target_pos], tlm_events[swap_pos] = (
                tlm_events[swap_pos],
                tlm_events[target_pos],
            )
            desc = f"{target.txn_id} and {tlm_events[target_pos].txn_id} swapped in order"
    else:
        raise ValueError(f"Unhandled mismatch type: {mismatch}")

    return tlm_events, InjectedMismatch(mismatch, target.txn_id, desc)


def generate_pair(
    n_transactions: int = 40,
    seed: Optional[int] = None,
    inject: Optional[MismatchType] = None,
) -> Tuple[str, str, Optional[InjectedMismatch]]:
    """
    Generate a matched RTL/TLM log pair.

    Returns (rtl_log_text, tlm_log_text, injected_mismatch_or_None).
    If `inject` is None, the TLM log is a perfect (mismatch-free) copy of RTL.
    """
    rng = random.Random(seed)
    rtl_events = _gen_base_events(n_transactions, rng)
    tlm_events = _clone_events(rtl_events)

    injected: Optional[InjectedMismatch] = None
    if inject is not None:
        tlm_events, injected = _inject_mismatch(tlm_events, inject, rng)

    rtl_text = "\n".join(e.to_line() for e in rtl_events)
    tlm_text = "\n".join(e.to_line() for e in tlm_events)
    return rtl_text, tlm_text, injected


def generate_regression_suite(
    n_logs: int = 50,
    n_transactions: int = 40,
    seed: int = 42,
) -> List[dict]:
    """
    Generate a full regression suite: n_logs pairs, cycling through the
    injectable failure types (mirrors the resume claim of "50 synthetic
    regression logs with 6 injected failure types").

    Roughly 1/7 of logs are "clean" (no injected mismatch) to test for
    false positives.
    """
    rng = random.Random(seed)
    failure_types = [m for m in MismatchType]  # all 7; resume says 6 -- see note below
    suite = []
    for i in range(n_logs):
        # ~15% clean logs to validate no false positives; rest cycle through mismatch types
        if i % 7 == 0:
            mismatch = None
        else:
            mismatch = failure_types[i % len(failure_types)]
        rtl, tlm, injected = generate_pair(
            n_transactions=n_transactions, seed=seed + i, inject=mismatch
        )
        suite.append(
            {
                "log_id": f"synthetic_{i:03d}",
                "rtl_log": rtl,
                "tlm_log": tlm,
                "injected": injected,
            }
        )
    return suite
