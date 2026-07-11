from app.alignment.aligner import align_events
from app.models import TraceSource
from app.parser.log_parser import parse_log_text
from app.parser.synthetic_generator import MismatchType, generate_pair


def _parse_pair(rtl_text: str, tlm_text: str):
    rtl_events = parse_log_text(rtl_text, TraceSource.RTL)
    tlm_events = parse_log_text(tlm_text, TraceSource.TLM)
    return rtl_events, tlm_events


class TestAligner:
    def test_clean_pair_aligns_everything_by_txn_id(self):
        rtl_text, tlm_text, _ = generate_pair(n_transactions=20, seed=1, inject=None)
        rtl_events, tlm_events = _parse_pair(rtl_text, tlm_text)

        result = align_events(rtl_events, tlm_events)

        assert len(result.missing_in_tlm) == 0
        assert len(result.extra_in_tlm) == 0
        assert all(not p.matched_by_fallback for p in result.aligned)
        # 20 transactions -> some are annotations, so aligned count should
        # equal however many non-annotation txns there actually are
        assert len(result.aligned) == len(rtl_events) - len(result.rtl_annotations)

    def test_missing_transaction_shows_up_as_missing_in_tlm(self):
        rtl_text, tlm_text, injected = generate_pair(
            n_transactions=20, seed=7, inject=MismatchType.MISSING_TRANSACTION
        )
        rtl_events, tlm_events = _parse_pair(rtl_text, tlm_text)

        result = align_events(rtl_events, tlm_events)

        assert len(result.missing_in_tlm) == 1
        assert result.missing_in_tlm[0].txn_id == injected.txn_id
        assert len(result.extra_in_tlm) == 0

    def test_extra_transaction_shows_up_as_extra_in_tlm(self):
        rtl_text, tlm_text, injected = generate_pair(
            n_transactions=20, seed=9, inject=MismatchType.EXTRA_TRANSACTION
        )
        rtl_events, tlm_events = _parse_pair(rtl_text, tlm_text)

        result = align_events(rtl_events, tlm_events)

        assert len(result.extra_in_tlm) == 1
        assert result.extra_in_tlm[0].txn_id == injected.txn_id
        assert len(result.missing_in_tlm) == 0

    def test_data_mismatch_still_aligns_by_txn_id(self):
        # A data mismatch shouldn't affect alignment at all -- the txn_id is
        # unchanged, only the payload differs. Alignment just pairs them up;
        # detecting the *difference* is the detection engine's job (next phase).
        rtl_text, tlm_text, injected = generate_pair(
            n_transactions=20, seed=5, inject=MismatchType.DATA_MISMATCH
        )
        rtl_events, tlm_events = _parse_pair(rtl_text, tlm_text)

        result = align_events(rtl_events, tlm_events)

        assert len(result.missing_in_tlm) == 0
        assert len(result.extra_in_tlm) == 0
        mismatched_pair = next(p for p in result.aligned if p.rtl_event.txn_id == injected.txn_id)
        assert mismatched_pair.rtl_event.data != mismatched_pair.tlm_event.data

    def test_annotations_excluded_from_alignment_but_preserved(self):
        rtl_text, tlm_text, _ = generate_pair(n_transactions=20, seed=1, inject=None)
        rtl_events, tlm_events = _parse_pair(rtl_text, tlm_text)

        result = align_events(rtl_events, tlm_events)

        assert len(result.rtl_annotations) > 0
        assert len(result.tlm_annotations) > 0
        aligned_txn_ids = {p.rtl_event.txn_id for p in result.aligned}
        assert "TXN0000" not in aligned_txn_ids  # annotations use this reserved id
