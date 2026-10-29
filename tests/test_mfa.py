"""
Automated Test Suite for MFA Physical Token Simulator.
Covers all functional, edge-case, security, and logging requirements.
"""

import time
import pytest
from unittest.mock import patch, MagicMock

from app import create_app
from config import TestingConfig, Config
from cloudwatch_logger import setup_logging


@pytest.fixture
def app():
    """Creates a test application instance with testing configuration."""
    test_app = create_app(TestingConfig)
    return test_app


@pytest.fixture
def client(app):
    """Provides a test client for simulating HTTP requests."""
    return app.test_client()


# ============================================================================
# 1. Frontend & Static File Tests
# ============================================================================

def test_home_page_loads_successfully(client):
    """Test 1: Home page (GET /) loads with HTTP 200 and expected HTML content."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"MFA Token Simulator" in response.data
    assert b"<!DOCTYPE html>" in response.data or b"<html" in response.data


def test_static_css_and_js_serve(client):
    """Verifies that static assets (style.css and script.js) serve correctly."""
    css_res = client.get("/style.css")
    assert css_res.status_code == 200
    assert "text/css" in css_res.headers.get("Content-Type", "")

    js_res = client.get("/script.js")
    assert js_res.status_code == 200
    assert "javascript" in js_res.headers.get("Content-Type", "")


# ============================================================================
# 2. Health & Status Endpoint Tests
# ============================================================================

def test_health_endpoint_works(client):
    """Test 2: Health check endpoint (GET /api/health) returns 200 and safe metadata."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()

    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "cloudwatch" in data
    assert "demo_mode" in data
    assert "otp_ttl_seconds" in data

    # Verify no sensitive credentials or internal paths are leaked
    data_str = str(data)
    assert "aws_access_key" not in data_str.lower()
    assert "secret_key" not in data_str.lower()
    assert "password" not in data_str.lower()


def test_status_endpoint(client):
    """Verifies that the /api/status endpoint returns real-time state safely."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.get_json()
    assert "has_active_otp" in data
    assert "remaining_seconds" in data
    assert "failed_attempts" in data


# ============================================================================
# 3. OTP Generation Tests
# ============================================================================

def test_otp_generation_demo_mode(client):
    """Test 3: OTP generation returns a valid six-digit OTP in demo mode."""
    response = client.post("/api/generate")
    assert response.status_code == 200
    data = response.get_json()

    assert data["success"] is True
    assert "otp" in data
    otp = str(data["otp"])
    assert len(otp) == 6
    assert otp.isdigit()
    assert 100000 <= int(otp) <= 999999
    assert data["ttl_seconds"] > 0
    assert "expires_at" in data


def test_otp_generation_non_demo_mode():
    """Verifies that when DEMO_SHOW_OTP is False, the OTP value is NOT returned."""
    class NonDemoConfig(TestingConfig):
        DEMO_SHOW_OTP = False

    non_demo_app = create_app(NonDemoConfig)
    test_client = non_demo_app.test_client()

    response = test_client.post("/api/generate")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data.get("otp") is None


# ============================================================================
# 4. OTP Verification Success & Failure Tests
# ============================================================================

def test_correct_otp_verification_succeeds(client):
    """Test 4: Correct OTP verification succeeds and returns HTTP 200."""
    gen_res = client.post("/api/generate")
    data = gen_res.get_json()
    valid_otp = data["otp"]

    verify_res = client.post("/api/verify", json={"otp": valid_otp})
    assert verify_res.status_code == 200
    verify_data = verify_res.get_json()
    assert verify_data["success"] is True
    assert "verified" in verify_data["message"].lower()


def test_incorrect_otp_is_rejected(client):
    """Test 5: Incorrect OTP is rejected with HTTP 400."""
    gen_res = client.post("/api/generate")
    valid_otp = gen_res.get_json()["otp"]

    # Generate an OTP that is definitely different
    wrong_otp = "999999" if valid_otp != "999999" else "111111"

    verify_res = client.post("/api/verify", json={"otp": wrong_otp})
    assert verify_res.status_code == 400
    verify_data = verify_res.get_json()
    assert verify_data["success"] is False
    assert "invalid" in verify_data["message"].lower()


def test_malformed_otp_rejected(client):
    """Test 6: Malformed OTP (non-numeric, wrong length, letters) is rejected with HTTP 400."""
    client.post("/api/generate")

    malformed_samples = [
        "12345",       # Too short
        "1234567",     # Too long
        "abcdef",      # Non-numeric
        "123 56",      # Spaces inside
        "!@#$%^",      # Symbols
        "",            # Empty string
    ]

    for sample in malformed_samples:
        res = client.post("/api/verify", json={"otp": sample})
        assert res.status_code == 400
        data = res.get_json()
        assert data["success"] is False


def test_missing_otp_handled_correctly(client):
    """Test 7: Missing OTP field or invalid payload is handled cleanly."""
    # Empty JSON object
    res1 = client.post("/api/verify", json={})
    assert res1.status_code == 400
    assert res1.get_json()["success"] is False

    # Missing JSON body entirely
    res2 = client.post("/api/verify", data="not json", content_type="text/plain")
    assert res2.status_code == 400
    assert res2.get_json()["success"] is False


def test_verification_without_active_otp(client):
    """Verification before generating an OTP must be rejected cleanly."""
    # Ensure simulator is reset
    client.post("/api/reset")

    res = client.post("/api/verify", json={"otp": "123456"})
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert "generate an otp first" in data["message"].lower() or "no active otp" in data["message"].lower()


# ============================================================================
# 5. Expiry & Single-Use Enforcement Tests
# ============================================================================

def test_expired_otp_is_rejected():
    """Test 8: Expired OTP is rejected and invalidated."""
    class FastExpiryConfig(TestingConfig):
        OTP_TTL_SECONDS = 1  # 1 second TTL

    short_app = create_app(FastExpiryConfig)
    short_client = short_app.test_client()

    gen_res = short_client.post("/api/generate")
    valid_otp = gen_res.get_json()["otp"]

    # Sleep slightly more than 1 second to trigger expiry
    time.sleep(1.2)

    verify_res = short_client.post("/api/verify", json={"otp": valid_otp})
    assert verify_res.status_code == 400
    data = verify_res.get_json()
    assert data["success"] is False
    assert "expired" in data["message"].lower()


def test_successfully_verified_otp_cannot_be_reused(client):
    """Test 9: Successfully verified OTP cannot be reused (single-use token)."""
    gen_res = client.post("/api/generate")
    valid_otp = gen_res.get_json()["otp"]

    # First verification must succeed
    res1 = client.post("/api/verify", json={"otp": valid_otp})
    assert res1.status_code == 200
    assert res1.get_json()["success"] is True

    # Immediate second verification with the same OTP must fail
    res2 = client.post("/api/verify", json={"otp": valid_otp})
    assert res2.status_code == 400
    assert res2.get_json()["success"] is False


def test_max_failed_attempts_lockout():
    """Verifies that exceeding MAX_VERIFY_ATTEMPTS invalidates the OTP."""
    class LowAttemptsConfig(TestingConfig):
        MAX_VERIFY_ATTEMPTS = 3

    attempt_app = create_app(LowAttemptsConfig)
    tclient = attempt_app.test_client()

    gen_res = tclient.post("/api/generate")
    correct_otp = gen_res.get_json()["otp"]
    wrong_otp = "000000" if correct_otp != "000000" else "111111"

    # Attempt 1: fail
    res1 = tclient.post("/api/verify", json={"otp": wrong_otp})
    assert res1.status_code == 400

    # Attempt 2: fail
    res2 = tclient.post("/api/verify", json={"otp": wrong_otp})
    assert res2.status_code == 400

    # Attempt 3: reached max limit, token should be locked/invalidated
    res3 = tclient.post("/api/verify", json={"otp": wrong_otp})
    assert res3.status_code == 400
    assert "exceeded" in res3.get_json()["message"].lower()

    # Attempt 4 with correct OTP should now fail because token was invalidated
    res4 = tclient.post("/api/verify", json={"otp": correct_otp})
    assert res4.status_code == 400


# ============================================================================
# 6. Abuse Prevention / Rate Limiting Tests
# ============================================================================

def test_rate_limits_behave_as_expected():
    """Test 10: Generation rate limiting blocks rapid repetitive requests with 429."""
    class RateLimitedConfig(TestingConfig):
        RATE_LIMIT_GENERATE_SECONDS = 3

    rl_app = create_app(RateLimitedConfig)
    rl_client = rl_app.test_client()

    # First request succeeds
    res1 = rl_client.post("/api/generate")
    assert res1.status_code == 200

    # Immediate second request fails with HTTP 429
    res2 = rl_client.post("/api/generate")
    assert res2.status_code == 429
    data2 = res2.get_json()
    assert data2["success"] is False
    assert "wait" in data2["message"].lower() or "rate" in data2["error"].lower()


# ============================================================================
# 7. CloudWatch & Logging Resiliency Tests
# ============================================================================

def test_cloudwatch_disabled_mode_works_without_credentials():
    """Test 11: CloudWatch disabled mode functions perfectly without AWS credentials."""
    class NoCWConfig(Config):
        CLOUDWATCH_ENABLED = False

    logger, cw_state = setup_logging(NoCWConfig)
    assert cw_state["enabled"] is False
    assert cw_state["status"] == "disabled"

    # Ensure application starts and processes requests normally
    test_app = create_app(NoCWConfig)
    test_client = test_app.test_client()

    health_res = test_client.get("/api/health")
    assert health_res.status_code == 200
    data = health_res.get_json()
    assert data["cloudwatch"]["enabled"] is False
    assert data["cloudwatch"]["status"] == "disabled"


def test_cloudwatch_init_failure_does_not_crash_app():
    """Test 12: AWS logging initialization failure falls back safely without crashing."""
    class BrokenCWConfig(Config):
        CLOUDWATCH_ENABLED = True
        AWS_DEFAULT_REGION = "invalid-region-99"

    # Simulate boto3 / watchtower throwing an authentication or connection error
    with patch("boto3.client") as mock_boto:
        mock_boto.side_effect = Exception("AWS Credentials Not Found: Unable to locate credentials")

        logger, cw_state = setup_logging(BrokenCWConfig)

        # CloudWatch state must reflect failure, not crash
        assert cw_state["enabled"] is False
        assert cw_state["status"] == "failed"
        assert "AWS Credentials Not Found" in cw_state["error"]

        # Ensure app still runs and functions normally
        broken_app = create_app(BrokenCWConfig)
        broken_client = broken_app.test_client()

        # OTP generation and verification must still work completely!
        gen_res = broken_client.post("/api/generate")
        assert gen_res.status_code == 200
        otp = gen_res.get_json()["otp"]

        verify_res = broken_client.post("/api/verify", json={"otp": otp})
        assert verify_res.status_code == 200
        assert verify_res.get_json()["success"] is True


# ============================================================================
# 8. Security Events & Reset Tests
# ============================================================================

def test_security_audit_events_endpoint(client):
    """Verifies that security events endpoint captures sanitized logs."""
    client.post("/api/generate")
    events_res = client.get("/api/events")
    assert events_res.status_code == 200
    data = events_res.get_json()
    assert data["success"] is True
    assert data["count"] > 0
    assert any(ev["event_type"] == "OTP_GENERATED" for ev in data["events"])


def test_reset_session_endpoint(client):
    """Verifies that the /api/reset endpoint clears active OTP sessions."""
    client.post("/api/generate")
    status1 = client.get("/api/status").get_json()
    assert status1["has_active_otp"] is True

    reset_res = client.post("/api/reset")
    assert reset_res.status_code == 200

    status2 = client.get("/api/status").get_json()
    assert status2["has_active_otp"] is False



# ============================================================================
# 9. Dashboard Analytics & Settings Tests
# ============================================================================

def test_dashboard_stats_endpoint(client):
    """Verifies that the /api/stats endpoint returns aggregated metrics and token metadata."""
    client.post("/api/generate")
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "metrics" in data["data"]
    assert "token_info" in data["data"]
    assert "session_status" in data["data"]
    assert "recent_attempts" in data["data"]
    assert data["data"]["metrics"]["total_generated"] >= 1


def test_settings_get_and_post(client):
    """Verifies reading and dynamically updating application settings."""
    # Read settings
    get_res = client.get("/api/settings")
    assert get_res.status_code == 200
    settings = get_res.get_json()["settings"]
    assert "otp_ttl_seconds" in settings

    # Update settings
    post_res = client.post("/api/settings", json={
        "otp_ttl_seconds": 60,
        "max_attempts": 3
    })
    assert post_res.status_code == 200
    assert post_res.get_json()["success"] is True

    # Confirm updated
    get_res2 = client.get("/api/settings")
    assert get_res2.get_json()["settings"]["otp_ttl_seconds"] == 60


def test_token_resync_and_clear_logs(client):
    """Verifies hardware token resync and clearing audit logs."""
    resync_res = client.post("/api/token/resync")
    assert resync_res.status_code == 200
    assert resync_res.get_json()["success"] is True

    clear_res = client.post("/api/logs/clear")
    assert clear_res.status_code == 200
    assert clear_res.get_json()["success"] is True
