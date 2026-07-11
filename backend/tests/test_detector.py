from app.alignment.aligner import align_events
from app.detection.detector import detect_mismatches
from app.models import TraceSource
from app.parser.log_parser import parse_log_text
from app.parser.synthetic_generator import MismatchType, generate_pair


def _detect(n_transactions, seed, inject):
    rtl_text, tlm_text, injected = generate_pair(
        n_transactions=n_transactions, seed=seed, inject=inject
    )
    rtl_events = parse_log_text(rtl_text, TraceSource.RTL)
    tlm_events = parse_log_text(tlm_text, TraceSource.TLM)
    result = align_events(rtl_events, tlm_events)
    findings = detect_mismatches(result)
    return findings, injected


class TestDetector:
    def test_clean_pair_has_no_findings(self):
        findings, injected = _detect(20, seed=1, inject=None)
        assert findings == []

    def test_data_mismatch_detected(self):
        findings, injected = _detect(20, seed=5, inject=MismatchType.DATA_MISMATCH)
        matches = [f for f in findings if f.mismatch_type == MismatchType.DATA_MISMATCH]
        assert len(matches) == 1
        assert matches[0].txn_ids == [injected.txn_id]

    def test_address_mismatch_detected(self):
        findings, injected = _detect(20, seed=3, inject=MismatchType.ADDRESS_MISMATCH)
        matches = [f for f in findings if f.mismatch_type == MismatchType.ADDRESS_MISMATCH]
        assert len(matches) == 1
        assert matches[0].txn_ids == [injected.txn_id]

    def test_state_mismatch_detected(self):
        findings, injected = _detect(20, seed=2, inject=MismatchType.STATE_MISMATCH)
        matches = [f for f in findings if f.mismatch_type == MismatchType.STATE_MISMATCH]
        assert len(matches) == 1
        assert matches[0].txn_ids == [injected.txn_id]

    def test_timing_mismatch_detected(self):
        findings, injected = _detect(20, seed=4, inject=MismatchType.TIMING_MISMATCH)
        matches = [f for f in findings if f.mismatch_type == MismatchType.TIMING_MISMATCH]
        assert len(matches) == 1
        assert matches[0].txn_ids == [injected.txn_id]

    def test_missing_transaction_detected(self):
        findings, injected = _detect(20, seed=7, inject=MismatchType.MISSING_TRANSACTION)
        matches = [f for f in findings if f.mismatch_type == MismatchType.MISSING_TRANSACTION]
        assert len(matches) == 1
        assert matches[0].txn_ids == [injected.txn_id]

    def test_extra_transaction_detected(self):
        findings, injected = _detect(20, seed=9, inject=MismatchType.EXTRA_TRANSACTION)
        matches = [f for f in findings if f.mismatch_type == MismatchType.EXTRA_TRANSACTION]
        assert len(matches) == 1
        assert matches[0].txn_ids == [injected.txn_id]

    def test_ordering_mismatch_detected(self):
        findings, injected = _detect(20, seed=11, inject=MismatchType.ORDERING_MISMATCH)
        matches = [f for f in findings if f.mismatch_type == MismatchType.ORDERING_MISMATCH]
        assert len(matches) >= 1

    def test_all_seven_mismatch_types_are_individually_detectable(self):
        for mismatch in MismatchType:
            findings, injected = _detect(20, seed=13, inject=mismatch)
            matches = [f for f in findings if f.mismatch_type == mismatch]
            assert len(matches) >= 1, f"{mismatch} was not detected"
