import pytest

from app.models import EventType, TraceSource
from app.parser.log_parser import LogParseError, parse_line, parse_log_text
from app.parser.synthetic_generator import (
    MismatchType,
    generate_pair,
    generate_regression_suite,
)


class TestParser:
    def test_parse_reg_write_line(self):
        event = parse_line(
            "1000 | TXN0001 | REG_WRITE | addr=0x1040 data=0xDEADBEEF", TraceSource.RTL
        )
        assert event.timestamp_ns == 1000
        assert event.txn_id == "TXN0001"
        assert event.event_type == EventType.REG_WRITE
        assert event.addr == "0x1040"
        assert event.data == "0xdeadbeef"

    def test_parse_annotation_line(self):
        event = parse_line("1500 | TXN0000 | ANNOTATION | note=HEADER_ERROR", TraceSource.TLM)
        assert event.is_annotation()
        assert event.note == "HEADER_ERROR"

    def test_parse_pkt_tx_with_state(self):
        event = parse_line(
            "1010 | TXN0003 | PKT_TX | data=A1B2C3D4 state=FILTER_ACTIVE", TraceSource.RTL
        )
        assert event.state == "FILTER_ACTIVE"

    def test_malformed_line_raises(self):
        with pytest.raises(LogParseError):
            parse_line("not a valid line", TraceSource.RTL)

    def test_unknown_event_type_raises(self):
        with pytest.raises(LogParseError):
            parse_line("1000 | TXN0001 | BOGUS_EVENT | addr=0x1", TraceSource.RTL)

    def test_parse_log_text_skips_blank_and_comment_lines(self):
        text = "# comment\n\n1000 | TXN0001 | REG_WRITE | addr=0x1 data=0x2\n"
        events = parse_log_text(text, TraceSource.RTL)
        assert len(events) == 1


class TestSyntheticGenerator:
    def test_clean_pair_is_identical(self):
        rtl_text, tlm_text, injected = generate_pair(n_transactions=20, seed=5, inject=None)
        assert rtl_text == tlm_text
        assert injected is None

    def test_data_mismatch_injection_differs_only_in_data(self):
        rtl_text, tlm_text, injected = generate_pair(
            n_transactions=20, seed=5, inject=MismatchType.DATA_MISMATCH
        )
        assert rtl_text != tlm_text
        assert injected.mismatch_type == MismatchType.DATA_MISMATCH
        assert len(rtl_text.splitlines()) == len(tlm_text.splitlines())

    def test_missing_transaction_removes_a_line(self):
        rtl_text, tlm_text, injected = generate_pair(
            n_transactions=20, seed=7, inject=MismatchType.MISSING_TRANSACTION
        )
        assert len(tlm_text.splitlines()) == len(rtl_text.splitlines()) - 1
        assert injected.txn_id not in tlm_text

    def test_extra_transaction_adds_a_line(self):
        rtl_text, tlm_text, injected = generate_pair(
            n_transactions=20, seed=9, inject=MismatchType.EXTRA_TRANSACTION
        )
        assert len(tlm_text.splitlines()) == len(rtl_text.splitlines()) + 1
        assert injected.txn_id in tlm_text
        assert injected.txn_id not in rtl_text

    def test_all_mismatch_types_produce_valid_parseable_logs(self):
        for mismatch in MismatchType:
            rtl_text, tlm_text, injected = generate_pair(
                n_transactions=15, seed=3, inject=mismatch
            )
            rtl_events = parse_log_text(rtl_text, TraceSource.RTL)
            tlm_events = parse_log_text(tlm_text, TraceSource.TLM)
            assert len(rtl_events) > 0
            assert len(tlm_events) > 0

    def test_regression_suite_generates_requested_count(self):
        suite = generate_regression_suite(n_logs=10, n_transactions=10, seed=1)
        assert len(suite) == 10
        for entry in suite:
            assert "rtl_log" in entry and "tlm_log" in entry
