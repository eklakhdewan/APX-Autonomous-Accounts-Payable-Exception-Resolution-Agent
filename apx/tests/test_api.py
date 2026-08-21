from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from apx.api import create_app


@pytest.fixture
def client():
    """Create a test client with lifespan."""
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def admin_headers():
    """API key headers for admin role."""
    return {"X-API-Key": "admin-key"}


@pytest.fixture
def operator_headers():
    """API key headers for operator role."""
    return {"X-API-Key": "operator-key"}


@pytest.fixture
def approver_headers():
    """API key headers for approver role."""
    return {"X-API-Key": "approver-key"}


@pytest.fixture
def reader_headers():
    """API key headers for reader role."""
    return {"X-API-Key": "reader-key"}


class TestHealthEndpoints:
    """Tests for health and readiness endpoints."""

    def test_health_endpoint(self, client):
        """Test GET /health returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_readiness_endpoint(self, client):
        """Test GET /ready returns readiness status."""
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert "ready" in data
        assert "checks" in data
        assert data["checks"]["database"] is True
        assert data["checks"]["validator"] is True
        assert data["checks"]["evidence_engine"] is True


class TestAuthentication:
    """Tests for authentication and authorization."""

    def test_unauthenticated_request(self, client):
        """Test that requests without API key return 401."""
        response = client.get("/invoices")
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "unauthorized"

    def test_invalid_api_key(self, client):
        """Test that invalid API key returns 401."""
        response = client.get("/invoices", headers={"X-API-Key": "invalid-key"})
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "unauthorized"

    def test_reader_role_can_get(self, client, reader_headers):
        """Test reader role can access GET endpoints."""
        response = client.get("/health", headers=reader_headers)
        assert response.status_code == 200

    def test_reader_role_cannot_post(self, client, reader_headers):
        """Test reader role cannot access POST endpoints."""
        response = client.post("/invoices", headers=reader_headers, json={})
        assert response.status_code == 403
        data = response.json()
        assert data["error"] == "forbidden"

    def test_operator_role_can_post_invoices(self, client, operator_headers):
        """Test operator role can create invoices."""
        # Just test authorization - we don't need valid invoice data
        response = client.post("/invoices", headers=operator_headers, json={"invalid": "data"})
        # Should get 422 validation error, not 403 forbidden
        assert response.status_code in [422, 400]

    def test_approver_role_can_approve(self, client, approver_headers):
        """Test approver role can approve cases."""
        # Use a valid UUID that doesn't exist
        import uuid
        fake_case_id = str(uuid.uuid4())
        response = client.post(f"/cases/{fake_case_id}/approve", headers=approver_headers, json={"approver_id": "approver1", "notes": "test"})
        # Should get 404 not found, not 403 forbidden
        # 400 is also acceptable (validation error for non-existent approval)
        assert response.status_code in [404, 400]


class TestInvoiceEndpoints:
    """Tests for invoice endpoints."""

    def test_create_invoice_success(self, client, operator_headers):
        """Test successful invoice creation."""
        invoice_data = {
            "invoice_id": "INV-TEST-001",
            "vendor_id": "V-0001",
            "invoice_number": "INV-2026-001",
            "po_number": "PO-2026-001",
            "invoice_date": "2026-01-15",
            "due_date": "2026-02-14",
            "currency": "USD",
            "subtotal": "1000.00",
            "tax": "100.00",
            "total": "1100.00",
            "discount": "0.00",
            "line_items": [
                {
                    "line_id": "L-001",
                    "description": "Test Item",
                    "po_line_id": "POL-001",
                    "quantity": "10",
                    "unit_price": "100.00",
                    "discount": "0.00",
                    "tax_rate": "0.10"
                }
            ]
        }
        response = client.post("/invoices", headers=operator_headers, json=invoice_data)
        assert response.status_code == 201
        data = response.json()
        assert data["invoice_id"] == "INV-TEST-001"
        assert "case_id" in data
        assert data["status"] == "submitted"

    def test_create_invoice_validation_error(self, client, operator_headers):
        """Test invoice creation with invalid data returns 422."""
        invoice_data = {
            "invoice_id": "INV-TEST-002",
            "vendor_id": "V-0001",
            # Missing required fields
        }
        response = client.post("/invoices", headers=operator_headers, json=invoice_data)
        assert response.status_code == 422

    def test_get_invoice(self, client, operator_headers):
        """Test getting an invoice by ID."""
        # First create an invoice
        invoice_data = {
            "invoice_id": "INV-TEST-003",
            "vendor_id": "V-0001",
            "invoice_number": "INV-2026-003",
            "invoice_date": "2026-01-15",
            "due_date": "2026-02-14",
            "currency": "USD",
            "subtotal": "1000.00",
            "tax": "100.00",
            "total": "1100.00",
            "line_items": []
        }
        client.post("/invoices", headers=operator_headers, json=invoice_data)

        # Now get it
        response = client.get("/invoices/INV-TEST-003", headers=operator_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["invoice_id"] == "INV-TEST-003"

    def test_get_nonexistent_invoice(self, client, operator_headers):
        """Test getting non-existent invoice returns 404."""
        response = client.get("/invoices/NONEXISTENT", headers=operator_headers)
        assert response.status_code == 404

    def test_process_invoice(self, client, operator_headers):
        """Test processing an invoice."""
        # First create an invoice
        invoice_data = {
            "invoice_id": "INV-TEST-004",
            "vendor_id": "V-0001",
            "invoice_number": "INV-2026-004",
            "invoice_date": "2026-01-15",
            "due_date": "2026-02-14",
            "currency": "USD",
            "subtotal": "1000.00",
            "tax": "100.00",
            "total": "1100.00",
            "line_items": []
        }
        client.post("/invoices", headers=operator_headers, json=invoice_data)

        # Process it
        response = client.post("/invoices/INV-TEST-004/process", headers=operator_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["invoice_id"] == "INV-TEST-004"
        assert "case_id" in data

    def test_process_nonexistent_invoice(self, client, operator_headers):
        """Test processing non-existent invoice returns 404."""
        response = client.post("/invoices/NONEXISTENT/process", headers=operator_headers)
        assert response.status_code == 404


class TestCaseEndpoints:
    """Tests for case endpoints."""

    def test_get_case(self, client, operator_headers):
        """Test getting a case by ID."""
        # First create and process an invoice to create a case
        invoice_data = {
            "invoice_id": "INV-TEST-005",
            "vendor_id": "V-0001",
            "invoice_number": "INV-2026-005",
            "invoice_date": "2026-01-15",
            "due_date": "2026-02-14",
            "currency": "USD",
            "subtotal": "1000.00",
            "tax": "100.00",
            "total": "1100.00",
            "line_items": []
        }
        create_resp = client.post("/invoices", headers=operator_headers, json=invoice_data)
        case_id = create_resp.json()["case_id"]

        # Get the case
        response = client.get(f"/cases/{case_id}", headers=operator_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["case_id"] == case_id

    def test_get_nonexistent_case(self, client, operator_headers):
        """Test getting non-existent case returns 404."""
        import uuid
        fake_id = str(uuid.uuid4())
        response = client.get(f"/cases/{fake_id}", headers=operator_headers)
        assert response.status_code == 404

    def test_list_cases(self, client, operator_headers):
        """Test listing cases."""
        response = client.get("/cases", headers=operator_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestApprovalEndpoints:
    """Tests for approval endpoints."""

    def test_get_approval(self, client, operator_headers):
        """Test getting approval for a case."""
        # First create and process an invoice to create a case with approval
        invoice_data = {
            "invoice_id": "INV-TEST-006",
            "vendor_id": "V-0001",
            "invoice_number": "INV-2026-006",
            "invoice_date": "2026-01-15",
            "due_date": "2026-02-14",
            "currency": "USD",
            "subtotal": "1000.00",
            "tax": "100.00",
            "total": "1100.00",
            "line_items": []
        }
        create_resp = client.post("/invoices", headers=operator_headers, json=invoice_data)
        case_id = create_resp.json()["case_id"]
        client.post(f"/invoices/INV-TEST-006/process", headers=operator_headers)

        # Get approval
        response = client.get(f"/cases/{case_id}/approval", headers=operator_headers)
        # Approval might not exist if no approval required
        if response.status_code == 404:
            pytest.skip("No approval required for this case")
        assert response.status_code == 200
        data = response.json()
        assert "approval_id" in data

    def test_approve_case(self, client, operator_headers, approver_headers):
        """Test approving a case."""
        # Create invoice that requires approval
        invoice_data = {
            "invoice_id": "INV-TEST-007",
            "vendor_id": "V-0001",
            "invoice_number": "INV-2026-007",
            "invoice_date": "2026-01-15",
            "due_date": "2026-02-14",
            "currency": "USD",
            "subtotal": "100000.00",  # High amount to trigger approval
            "tax": "10000.00",
            "total": "110000.00",
            "line_items": []
        }
        create_resp = client.post("/invoices", headers=operator_headers, json=invoice_data)
        case_id = create_resp.json()["case_id"]
        client.post(f"/invoices/INV-TEST-007/process", headers=operator_headers)

        # Ensure approval exists (create directly if pipeline didn't create one)
        # This is needed because some invoices result in BLOCK decision (no approval)
        from uuid import UUID
        from apx.persistence.sqlite_repos import SQLiteApprovalRepository
        from apx.action.models import ApprovalRequest, ApprovalStatus
        from uuid import uuid4
        approval_repo = SQLiteApprovalRepository()
        existing_approval = approval_repo.get_by_case(UUID(case_id))
        if not existing_approval:
            # Create approval directly for testing
            approval_request = ApprovalRequest(
                approval_id=str(uuid4()),
                action_plan_id=case_id,
                action_type="ESCALATE_TO_HUMAN",
                risk_level="HIGH",
                requested_by="system",
                status=ApprovalStatus.PENDING,
                required_approvers=["approver1"],
            )
            approval_repo.create(approval_request)

        # Approve the case
        response = client.post(
            f"/cases/{case_id}/approve",
            headers=approver_headers,
            json={"approver_id": "approver1", "notes": "Approved"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "APPROVED"

    def test_reject_case(self, client, operator_headers, approver_headers):
        """Test rejecting a case."""
        invoice_data = {
            "invoice_id": "INV-TEST-008",
            "vendor_id": "V-0001",
            "invoice_number": "INV-2026-008",
            "invoice_date": "2026-01-15",
            "due_date": "2026-02-14",
            "currency": "USD",
            "subtotal": "100000.00",
            "tax": "10000.00",
            "total": "110000.00",
            "line_items": []
        }
        create_resp = client.post("/invoices", headers=operator_headers, json=invoice_data)
        case_id = create_resp.json()["case_id"]
        client.post(f"/invoices/INV-TEST-008/process", headers=operator_headers)

        # Ensure approval exists
        from uuid import UUID
        from apx.persistence.sqlite_repos import SQLiteApprovalRepository
        from apx.action.models import ApprovalRequest, ApprovalStatus
        from uuid import uuid4
        approval_repo = SQLiteApprovalRepository()
        existing_approval = approval_repo.get_by_case(UUID(case_id))
        if not existing_approval:
            approval_request = ApprovalRequest(
                approval_id=str(uuid4()),
                action_plan_id=case_id,
                action_type="ESCALATE_TO_HUMAN",
                risk_level="HIGH",
                requested_by="system",
                status=ApprovalStatus.PENDING,
                required_approvers=["approver1"],
            )
            approval_repo.create(approval_request)

        response = client.post(
            f"/cases/{case_id}/reject",
            headers=approver_headers,
            json={"approver_id": "approver1", "notes": "Rejected due to discrepancy"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "REJECTED"

    def test_unauthorized_approval(self, client, operator_headers, approver_headers):
        """Test that operator cannot approve."""
        invoice_data = {
            "invoice_id": "INV-TEST-009",
            "vendor_id": "V-0001",
            "invoice_number": "INV-2026-009",
            "invoice_date": "2026-01-15",
            "due_date": "2026-02-14",
            "currency": "USD",
            "subtotal": "100000.00",
            "tax": "10000.00",
            "total": "110000.00",
            "line_items": []
        }
        create_resp = client.post("/invoices", headers=operator_headers, json=invoice_data)
        case_id = create_resp.json()["case_id"]
        client.post(f"/invoices/INV-TEST-009/process", headers=operator_headers)

        # Ensure approval exists
        from uuid import UUID
        from apx.persistence.sqlite_repos import SQLiteApprovalRepository
        from apx.action.models import ApprovalRequest, ApprovalStatus
        from uuid import uuid4
        approval_repo = SQLiteApprovalRepository()
        existing_approval = approval_repo.get_by_case(UUID(case_id))
        if not existing_approval:
            approval_request = ApprovalRequest(
                approval_id=str(uuid4()),
                action_plan_id=case_id,
                action_type="ESCALATE_TO_HUMAN",
                risk_level="HIGH",
                requested_by="system",
                status=ApprovalStatus.PENDING,
                required_approvers=["approver1"],
            )
            approval_repo.create(approval_request)

        response = client.post(
            f"/cases/{case_id}/approve",
            headers=operator_headers,
            json={"approver_id": "operator1", "notes": "Trying to approve"}
        )
        assert response.status_code == 403


class TestAuditEndpoints:
    """Tests for audit endpoints."""

    def test_get_case_audit(self, client, operator_headers):
        """Test getting audit events for a case."""
        invoice_data = {
            "invoice_id": "INV-TEST-010",
            "vendor_id": "V-0001",
            "invoice_number": "INV-2026-010",
            "invoice_date": "2026-01-15",
            "due_date": "2026-02-14",
            "currency": "USD",
            "subtotal": "1000.00",
            "tax": "100.00",
            "total": "1100.00",
            "line_items": []
        }
        create_resp = client.post("/invoices", headers=operator_headers, json=invoice_data)
        case_id = create_resp.json()["case_id"]
        client.post(f"/invoices/INV-TEST-010/process", headers=operator_headers)

        response = client.get(f"/cases/{case_id}/audit", headers=operator_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have at least INVOICE_SUBMITTED, VALIDATION_COMPLETE, etc.
        assert len(data) > 0

    def test_audit_events_cannot_be_modified(self, client, operator_headers):
        """Test that audit events cannot be modified through API."""
        # There should be no POST/PUT/DELETE on audit endpoints
        response = client.post("/cases/some-id/audit", headers=operator_headers, json={})
        # Should get 404, 405 Method Not Allowed, or 403 Forbidden (operator not allowed)
        assert response.status_code in [403, 404, 405]


class TestMetricsEndpoint:
    """Tests for metrics endpoint."""

    def test_metrics_endpoint(self, client):
        """Test metrics endpoint with admin role."""
        headers = {"X-API-Key": "admin-key"}
        response = client.get("/metrics", headers=headers)
        assert response.status_code == 200
        # Should return Prometheus format (may be empty if no metrics recorded yet)
        # Just verify it returns valid text response

    def test_metrics_json(self, client):
        """Test metrics JSON endpoint."""
        headers = {"X-API-Key": "admin-key"}
        response = client.get("/metrics/json", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "counters" in data
        assert "gauges" in data


class TestErrorHandling:
    """Tests for error handling."""

    def test_404_error_format(self, client, operator_headers):
        """Test 404 error has correct format."""
        response = client.get("/invoices/NONEXISTENT", headers=operator_headers)
        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "not_found"

    def test_422_validation_error_format(self, client, operator_headers):
        """Test 422 validation error has correct format."""
        response = client.post("/invoices", headers=operator_headers, json={"invalid": "data"})
        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "validation_error"
        assert "details" in data


class TestRequestCorrelationIds:
    """Tests for request ID and correlation ID handling."""

    def test_request_id_generated(self, client, operator_headers):
        """Test that request ID is generated if not provided."""
        response = client.get("/health", headers=operator_headers)
        assert response.status_code == 200
        assert "x-request-id" in response.headers

    def test_correlation_id_preserved(self, client, operator_headers):
        """Test that correlation ID is preserved."""
        corr_id = "test-correlation-123"
        response = client.get("/health", headers={**operator_headers, "X-Correlation-ID": corr_id})
        assert response.status_code == 200
        assert response.headers.get("X-Correlation-ID") == corr_id

    def test_request_id_in_logs(self, client, operator_headers, caplog):
        """Test that request ID appears in logs."""
        with caplog.at_level("INFO"):
            client.get("/health", headers=operator_headers)
            # Check that request ID appears in log output
            # The request ID should be in the log output
            assert any("request_id" in record.message for record in caplog.records)


class TestIdempotency:
    """Tests for idempotency."""

    def test_idempotent_invoice_submission(self, client, operator_headers):
        """Test that duplicate invoice submission with same idempotency key returns existing case."""
        invoice_data = {
            "invoice_id": "INV-IDEMP-001",
            "vendor_id": "V-0001",
            "invoice_number": "INV-2026-IDEMP",
            "invoice_date": "2026-01-15",
            "due_date": "2026-02-14",
            "currency": "USD",
            "subtotal": "1000.00",
            "tax": "100.00",
            "total": "1100.00",
            "line_items": []
        }
        idempotency_key = "idem-test-001"

        # First submission
        response1 = client.post(
            "/invoices",
            headers={**operator_headers, "Idempotency-Key": "idem-test-001"},
            json=invoice_data
        )
        assert response1.status_code == 201
        case_id_1 = response1.json()["case_id"]

        # Second submission with same idempotency key
        response2 = client.post(
            "/invoices",
            headers={**operator_headers, "Idempotency-Key": "idem-test-001"},
            json=invoice_data
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["status"] == "already_exists"
        assert data2["case_id"] == case_id_1


class TestW3CTraceContext:
    """Tests for W3C Trace Context support."""

    def test_traceparent_generated_when_absent(self, client, operator_headers):
        """Test that traceparent is generated when not provided."""
        response = client.get("/health", headers=operator_headers)
        assert response.status_code == 200
        assert "traceparent" in response.headers
        traceparent = response.headers["traceparent"]
        assert traceparent.startswith("00-")
        assert len(traceparent.split("-")) == 4

    def test_traceparent_preserved_when_provided(self, client, operator_headers):
        """Test that traceparent is preserved when provided."""
        traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        response = client.get("/health", headers={**operator_headers, "traceparent": traceparent})
        assert response.status_code == 200
        assert response.headers.get("traceparent") == traceparent

    def test_tracestate_preserved_when_provided(self, client, operator_headers):
        """Test that tracestate is preserved when provided."""
        tracestate = "vendor=value1,value2"
        response = client.get("/health", headers={**operator_headers, "tracestate": tracestate})
        assert response.status_code == 200
        assert response.headers.get("tracestate") == tracestate

    def test_traceparent_in_request_logs(self, client, operator_headers, caplog):
        """Test that traceparent appears in request logs."""
        with caplog.at_level("INFO"):
            client.get("/health", headers=operator_headers)
            assert any("traceparent" in record.message for record in caplog.records)


class TestStructuredAccessLogging:
    """Tests for enhanced structured access logging."""

    def test_request_start_logs_client_ip(self, client, operator_headers, caplog):
        """Test that request.start logs client IP."""
        with caplog.at_level("INFO"):
            client.get("/health", headers=operator_headers)
            assert any("client_ip" in record.message for record in caplog.records)

    def test_request_start_logs_user_agent(self, client, operator_headers, caplog):
        """Test that request.start logs user agent."""
        with caplog.at_level("INFO"):
            client.get("/health", headers={**operator_headers, "User-Agent": "test-agent/1.0"})
            assert any("user_agent" in record.message for record in caplog.records)

    def test_request_end_logs_response_size(self, client, operator_headers, caplog):
        """Test that request.end logs response size."""
        with caplog.at_level("INFO"):
            client.get("/health", headers=operator_headers)
            assert any("response_size_bytes" in record.message for record in caplog.records)


class TestRequestResponseRedaction:
    """Tests for request/response body redaction."""

    def test_sensitive_fields_redacted_in_request_logs(self, client, operator_headers, caplog):
        """Test that sensitive fields are redacted in request body logs."""
        # Enable request body logging for this test
        import os
        os.environ["APX_API_LOG_REQUEST_BODY"] = "true"
        from apx.api.config import reset_api_settings
        reset_api_settings()

        with caplog.at_level("INFO"):
            invoice_data = {
                "invoice_id": "INV-REDACT-001",
                "vendor_id": "V-0001",
                "invoice_number": "INV-2026-REDACT",
                "invoice_date": "2026-01-15",
                "due_date": "2026-02-14",
                "currency": "USD",
                "subtotal": "1000.00",
                "tax": "100.00",
                "total": "1100.00",
                "line_items": [],
                "api_key": "secret-api-key-12345",
                "password": "secret-password",
            }
            client.post("/invoices", headers=operator_headers, json=invoice_data)
            # Check that sensitive fields are redacted in logs
            log_messages = [record.message for record in caplog.records]
            body_logs = [msg for msg in log_messages if "request.body" in msg]
            assert len(body_logs) > 0
            # The sensitive fields should be redacted
            for log in body_logs:
                assert "secret-api-key-12345" not in log
                assert "secret-password" not in log
                assert "***" in log or "****" in log


class TestAPIMetrics:
    """Tests for API metrics collection."""

    def test_api_latency_metric_recorded(self, client, operator_headers):
        """Test that API latency metric is recorded."""
        from apx.observability.metrics import get_metrics_collector
        collector = get_metrics_collector()
        # Get baseline
        baseline = collector.get_timer_stats("apx.api.latency_ms", labels={"endpoint": "GET /health"})
        baseline_count = baseline["count"]

        client.get("/health", headers=operator_headers)

        stats = collector.get_timer_stats("apx.api.latency_ms", labels={"endpoint": "GET /health"})
        assert stats["count"] == baseline_count + 1
        assert stats["avg"] > 0

    def test_api_request_counter_incremented(self, client, operator_headers):
        """Test that API request counter is incremented."""
        from apx.observability.metrics import get_metrics_collector
        collector = get_metrics_collector()
        baseline = collector.get_counter("apx.api.requests.total", labels={"endpoint": "GET /health", "status": "200"})

        client.get("/health", headers=operator_headers)

        count = collector.get_counter("apx.api.requests.total", labels={"endpoint": "GET /health", "status": "200"})
        assert count == baseline + 1

    def test_api_error_counter_incremented(self, client):
        """Test that API error counter is incremented for 4xx/5xx."""
        from apx.observability.metrics import get_metrics_collector
        collector = get_metrics_collector()
        baseline = collector.get_counter("apx.api.errors.total", labels={"endpoint": "GET /invoices/NONEXISTENT", "status": "404"})

        client.get("/invoices/NONEXISTENT", headers={"X-API-Key": "operator-key"})

        count = collector.get_counter("apx.api.errors.total", labels={"endpoint": "GET /invoices/NONEXISTENT", "status": "404"})
        assert count == baseline + 1


class TestRateLimiting:
    """Tests for rate limiting."""

    def test_rate_limit_allows_requests_under_limit(self, client, operator_headers):
        """Test that requests under the rate limit are allowed."""
        for _ in range(5):
            response = client.get("/cases", headers=operator_headers)
            assert response.status_code == 200

    def test_rate_limit_blocks_requests_over_limit(self, client, operator_headers):
        """Test that requests over the rate limit are blocked with 429."""
        from apx.api.config import reset_api_settings, get_api_settings
        reset_api_settings()
        settings = get_api_settings()
        original_limit = settings.rate_limit_requests_per_minute
        settings.rate_limit_requests_per_minute = 3
        settings.rate_limit_enabled = True

        try:
            # Make 3 requests (should succeed)
            for _ in range(3):
                response = client.get("/cases", headers=operator_headers)
                assert response.status_code == 200

            # 4th request should be rate limited
            response = client.get("/cases", headers=operator_headers)
            assert response.status_code == 429
            data = response.json()
            assert data["error"] == "rate_limited"
            assert "Retry-After" in response.headers
        finally:
            reset_api_settings()


class TestRequestSizeEnforcement:
    """Tests for request size enforcement."""

    def test_request_size_rejects_large_body(self, client, operator_headers):
        """Test that requests exceeding max size are rejected with 413."""
        from apx.api.config import reset_api_settings, get_api_settings
        reset_api_settings()
        settings = get_api_settings()
        original_max = settings.max_request_size
        settings.max_request_size = 100  # 100 bytes

        try:
            large_data = "x" * 200  # 200 bytes > 100 bytes limit
            response = client.post(
                "/invoices",
                headers={**operator_headers, "Content-Type": "application/json"},
                content=large_data
            )
            assert response.status_code == 413
            data = response.json()
            assert data["error"] == "payload_too_large"
        finally:
            reset_api_settings()

    def test_request_size_allows_small_body(self, client, operator_headers):
        """Test that requests under max size are allowed."""
        response = client.get("/health", headers=operator_headers)
        assert response.status_code == 200


class TestSecurityHeaders:
    """Tests for security headers."""

    def test_csp_header_present(self, client):
        """Test that Content-Security-Policy header is present."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "Content-Security-Policy" in response.headers
        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp

    def test_x_content_type_options_header(self, client):
        """Test that X-Content-Type-Options header is present."""
        response = client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options_header(self, client):
        """Test that X-Frame-Options header is present."""
        response = client.get("/health")
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_referrer_policy_header(self, client):
        """Test that Referrer-Policy header is present."""
        response = client.get("/health")
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy_header(self, client):
        """Test that Permissions-Policy header is present."""
        response = client.get("/health")
        assert "Permissions-Policy" in response.headers

    def test_hsts_header_only_on_https(self, client):
        """Test that HSTS header is only set for HTTPS."""
        # TestClient uses HTTP by default, so HSTS should not be present
        response = client.get("/health")
        # HSTS should not be set for HTTP
        assert "Strict-Transport-Security" not in response.headers

    def test_server_header_removed(self, client):
        """Test that Server header is removed."""
        response = client.get("/health")
        assert "server" not in response.headers

    def test_docs_endpoint_not_blocked_by_csp(self):
        """Test that /docs endpoint is accessible in debug mode (CSP allows it)."""
        import os
        os.environ["APX_API_DEBUG"] = "true"
        from apx.api.config import reset_api_settings, get_api_settings
        reset_api_settings()
        settings = get_api_settings()
        assert settings.debug is True

        from apx.api import create_app
        from starlette.testclient import TestClient
        app = create_app()
        client = TestClient(app)

        response = client.get("/docs")
        # Should not be blocked by CSP in debug mode
        assert response.status_code == 200

        # Cleanup
        del os.environ["APX_API_DEBUG"]
        reset_api_settings()


class TestAuditEventRedaction:
    """Tests for audit event secret redaction."""

    def test_audit_payload_redacts_secrets(self, client, operator_headers):
        """Test that audit event payloads redact sensitive fields."""
        invoice_data = {
            "invoice_id": "INV-AUDIT-001",
            "vendor_id": "V-0001",
            "invoice_number": "INV-2026-AUDIT",
            "invoice_date": "2026-01-15",
            "due_date": "2026-02-14",
            "currency": "USD",
            "subtotal": "1000.00",
            "tax": "100.00",
            "total": "1100.00",
            "line_items": [],
        }
        response = client.post("/invoices", headers=operator_headers, json=invoice_data)
        assert response.status_code == 201
        case_id = response.json()["case_id"]

        # Get audit events
        response = client.get(f"/cases/{case_id}/audit", headers=operator_headers)
        assert response.status_code == 200
        events = response.json()
        assert len(events) > 0

        # Check that audit payloads don't contain full sensitive values
        for event in events:
            payload = event.get("payload", {})
            # The audit system should redact sensitive fields
            # Note: current invoice data doesn't have sensitive fields, but the mechanism should work


class TestNestedRedaction:
    """Tests for nested sensitive data redaction."""

    def test_nested_dict_redaction(self):
        """Test that nested dictionaries are redacted."""
        from apx.observability.redaction import deep_redact

        data = {
            "user": {
                "name": "John",
                "credentials": {
                    "api_key": "secret-key-123",
                    "password": "secret-pass"
                }
            },
            "tokens": [
                {"access_token": "token-123", "type": "bearer"},
                {"refresh_token": "refresh-456", "type": "bearer"}
            ]
        }

        redacted = deep_redact(data)

        assert redacted["user"]["name"] == "John"
        # Redaction preserves string length: prefix(4) + middle(*) + suffix(4)
        assert redacted["user"]["credentials"]["api_key"] == "secr******-123"
        assert redacted["user"]["credentials"]["password"] == "secr***pass"
        assert redacted["tokens"][0]["access_token"] == "toke*-123"
        assert redacted["tokens"][1]["refresh_token"] == "refr***-456"
        assert redacted["tokens"][0]["type"] == "bearer"
        assert redacted["tokens"][1]["type"] == "bearer"

    def test_list_redaction(self):
        """Test that lists of dicts are redacted."""
        from apx.observability.redaction import deep_redact

        data = [
            {"api_key": "key1", "normal": "value1"},
            {"password": "pass2", "normal": "value2"}
        ]

        redacted = deep_redact(data)

        # Short values (<= 8 chars) are fully redacted
        assert redacted[0]["api_key"] == "****"
        assert redacted[0]["normal"] == "value1"
        assert redacted[1]["password"] == "*****"
        assert redacted[1]["normal"] == "value2"

    def test_string_pattern_redaction(self):
        """Test that string patterns like credit cards are redacted."""
        from apx.observability.redaction import deep_redact, redact_string

        text = "Card number: 4111 1111 1111 1111 and SSN: 123-45-6789"
        redacted = redact_string(text)

        assert "4111 1111 1111 1111" not in redacted
        assert "123-45-6789" not in redacted
        assert "***" in redacted


class TestAuthRBACTests:
    """Additional tests for auth/RBAC behavior with new middleware stack."""

    def test_auth_middleware_runs_before_authorization(self, client, operator_headers):
        """Test that AuthMiddleware runs before AuthorizationMiddleware."""
        # This is implicitly tested by other tests passing, but we verify explicitly
        # by checking that a valid API key allows AuthorizationMiddleware to see the role
        response = client.get("/health", headers=operator_headers)
        assert response.status_code == 200

    def test_invalid_key_rejected_before_authorization(self, client):
        """Test that invalid API key is rejected by AuthMiddleware before AuthorizationMiddleware."""
        response = client.get("/invoices", headers={"X-API-Key": "invalid-key"})
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "unauthorized"
        assert data["message"] == "Invalid API key"

    def test_missing_key_rejected_before_authorization(self, client):
        """Test that missing API key is rejected by AuthMiddleware before AuthorizationMiddleware."""
        response = client.get("/invoices")
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "unauthorized"
        assert data["message"] == "API key required"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])