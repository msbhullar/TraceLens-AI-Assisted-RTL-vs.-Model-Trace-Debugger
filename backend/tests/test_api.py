from fastapi.testclient import TestClient

from app.main import app
from app.parser.synthetic_generator import MismatchType, generate_pair

client = TestClient(app)


class TestHealthCheck:
    def test_health_check_returns_ok(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestAnalyzeEndpoint:
    def test_clean_logs_return_no_findings(self):
        rtl_text, tlm_text, _ = generate_pair(n_transactions=20, seed=1, inject=None)
        response = client.post(
            "/analyze",
            json={"rtl_log": rtl_text, "tlm_log": tlm_text, "timing_threshold_ns": 100},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total_findings"] == 0
        assert body["first_divergence"] is None
        assert body["timeline"] == []

    def test_state_mismatch_detected_via_api(self):
        rtl_text, tlm_text, injected = generate_pair(
            n_transactions=15, seed=2, inject=MismatchType.STATE_MISMATCH
        )
        response = client.post(
            "/analyze",
            json={"rtl_log": rtl_text, "tlm_log": tlm_text, "timing_threshold_ns": 100},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total_findings"] == 1
        assert body["first_divergence"]["mismatch_type"] == "STATE_MISMATCH"
        assert body["first_divergence"]["txn_ids"] == [injected.txn_id]

    def test_missing_transaction_detected_via_api(self):
        rtl_text, tlm_text, injected = generate_pair(
            n_transactions=20, seed=7, inject=MismatchType.MISSING_TRANSACTION
        )
        response = client.post(
            "/analyze",
            json={"rtl_log": rtl_text, "tlm_log": tlm_text, "timing_threshold_ns": 100},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["first_divergence"]["mismatch_type"] == "MISSING_TRANSACTION"
        assert body["first_divergence"]["txn_ids"] == [injected.txn_id]

    def test_malformed_log_returns_error_not_crash(self):
        response = client.post(
            "/analyze",
            json={"rtl_log": "not a valid log line", "tlm_log": "", "timing_threshold_ns": 100},
        )
        # We expect this to fail gracefully (4xx/5xx), not silently succeed
        # with garbage data. Exact status code isn't the point here -- the
        # point is the server doesn't crash the whole process.
        assert response.status_code in (400, 422, 500)
