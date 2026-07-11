from app.alignment.aligner import align_events
from app.detection.detector import Finding, detect_mismatches
from app.localization.localizer import localize
from app.models import TraceSource
from app.parser.log_parser import parse_log_text
from app.parser.synthetic_generator import MismatchType, generate_pair


def _run_pipeline(n_transactions, seed, inject):
    rtl_text, tlm_text, injected = generate_pair(
        n_transactions=n_transactions, seed=seed, inject=inject
    )
    rtl_events = parse_log_text(rtl_text, TraceSource.RTL)
    tlm_events = parse_log_text(tlm_text, TraceSource.TLM)
    result = align_events(rtl_events, tlm_events)
    findings = detect_mismatches(result)
    return result, findings, injected


class TestLocalizer:
    def test_no_findings_returns_none(self):
        result, findings, _ = _run_pipeline(20, seed=1, inject=None)
        loc = localize(result, findings)
        assert loc.first_divergence is None
        assert loc.timeline == []

    def test_single_mismatch_is_first_divergence(self):
        result, findings, injected = _run_pipeline(20, seed=5, inject=MismatchType.DATA_MISMATCH)
        loc = localize(result, findings)

        assert loc.first_divergence is not None
        assert loc.first_divergence.finding.txn_ids == [injected.txn_id]
        assert loc.first_divergence.finding.mismatch_type == MismatchType.DATA_MISMATCH

    def test_timeline_is_sorted_earliest_first(self):
        result, findings, injected = _run_pipeline(30, seed=8, inject=MismatchType.TIMING_MISMATCH)
        loc = localize(result, findings)

        timestamps = [tf.timestamp_ns for tf in loc.timeline]
        assert timestamps == sorted(timestamps)

    def test_picks_earlier_of_two_manually_constructed_findings(self):
        # Build a scenario with two findings at known, different
        # timestamps to directly verify the "earliest wins" logic,
        # independent of what the generator happens to produce.
        result, findings, injected = _run_pipeline(30, seed=12, inject=MismatchType.DATA_MISMATCH)

        # Manually fabricate a second finding for an earlier-occurring
        # transaction (TXN0001 always starts near t=1000ns, before whatever
        # the generator injected the real mismatch into).
        fabricated = Finding(
            mismatch_type=MismatchType.ADDRESS_MISMATCH,
            txn_ids=["TXN0001"],
            description="fabricated early finding for test purposes",
        )
        combined_findings = findings + [fabricated]

        loc = localize(result, combined_findings)

        # The fabricated TXN0001 finding should now be the first divergence,
        # since TXN0001 is always the earliest transaction in any generated log.
        assert loc.first_divergence.finding.txn_ids == ["TXN0001"]
        assert loc.timeline[0].finding.txn_ids == ["TXN0001"]
