"""
MFA Physical Token Simulator - Automated System Verification Script.
Runs comprehensive diagnostics against the application, verifying backend health,
CSPRNG generation, single-use replay protection, lockout policies, and telemetry.

Usage:
    python verify_system.py
"""

import sys
import time

# Configure standard output to UTF-8 or fallback safely on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def print_header(title):
    print("\n" + "=" * 65)
    print(f" {title}")
    print("=" * 65)


def print_result(check_name, passed, details=""):
    status = "[PASS]" if passed else "[FAIL]"
    print(f" {status} {check_name}")
    if details:
        print(f"        |-- {details}")


def main():
    print_header("MFA PHYSICAL TOKEN SIMULATOR - SYSTEM VERIFICATION")
    passed_count = 0
    total_checks = 7

    # 1. Dependency & Module Imports
    try:
        from app import create_app
        from config import TestingConfig
        import secrets
        import boto3
        import watchtower
        print_result("1. Python Dependencies & Core Modules", True, "Flask, secrets, boto3, watchtower loaded")
        passed_count += 1
    except Exception as e:
        print_result("1. Python Dependencies & Core Modules", False, str(e))
        return

    # 2. Application Factory Initialization
    try:
        app = create_app(TestingConfig)
        client = app.test_client()
        print_result("2. Flask Application Factory", True, "App instance initialized with TestingConfig")
        passed_count += 1
    except Exception as e:
        print_result("2. Flask Application Factory", False, str(e))
        return

    # 3. Health & Telemetry Gateway
    try:
        res = client.get("/api/health")
        data = res.get_json()
        assert res.status_code == 200
        assert data["status"] == "healthy"
        print_result("3. System Health Gateway (/api/health)", True, f"Status: {data['status']}, DemoMode: {data['demo_mode']}")
        passed_count += 1
    except Exception as e:
        print_result("3. System Health Gateway (/api/health)", False, str(e))

    # 4. Cryptographic OTP Generation (CSPRNG)
    otp = None
    try:
        res = client.post("/api/generate")
        data = res.get_json()
        assert res.status_code == 200
        assert data["success"] is True
        otp = data["otp"]
        assert len(otp) == 6 and otp.isdigit()
        print_result("4. Cryptographic OTP Generation (/api/generate)", True, f"Generated valid 6-digit CSPRNG token: {otp[:2]}****")
        passed_count += 1
    except Exception as e:
        print_result("4. Cryptographic OTP Generation (/api/generate)", False, str(e))

    # 5. OTP Verification & Single-Use Replay Protection
    try:
        # First verification must succeed
        res1 = client.post("/api/verify", json={"otp": otp})
        assert res1.status_code == 200
        assert res1.get_json()["success"] is True

        # Second verification with exact same OTP must fail (Replay attack defense)
        res2 = client.post("/api/verify", json={"otp": otp})
        assert res2.status_code == 400
        assert res2.get_json()["success"] is False
        print_result("5. Single-Use Replay Protection (/api/verify)", True, "Token consumed on 1st verify; re-submission strictly rejected (400)")
        passed_count += 1
    except Exception as e:
        print_result("5. Single-Use Replay Protection (/api/verify)", False, str(e))

    # 6. Brute-Force Lockout Defense
    try:
        # Generate new token
        gen_res = client.post("/api/generate")
        valid_otp = gen_res.get_json()["otp"]

        # Submit wrong OTPs until lockout
        for _ in range(5):
            client.post("/api/verify", json={"otp": "000000" if valid_otp != "000000" else "111111"})

        # Now correct OTP should be rejected because token was destroyed on lockout
        res_locked = client.post("/api/verify", json={"otp": valid_otp})
        assert res_locked.status_code == 400
        print_result("6. Brute-Force Lockout Policy", True, "Token invalidated after 5 failed attempts (lockout enforced)")
        passed_count += 1
    except Exception as e:
        print_result("6. Brute-Force Lockout Policy", False, str(e))

    # 7. Dashboard Metrics & Audit Telemetry Feed
    try:
        stats_res = client.get("/api/stats")
        stats_data = stats_res.get_json()["data"]
        events_res = client.get("/api/events")
        events_data = events_res.get_json()

        assert stats_res.status_code == 200
        assert stats_data["metrics"]["total_generated"] >= 2
        assert events_data["count"] > 0
        print_result("7. Telemetry & Audit Stream (/api/stats, /api/events)", True, f"Recorded {stats_data['metrics']['total_generated']} tokens, {events_data['count']} audit events")
        passed_count += 1
    except Exception as e:
        print_result("7. Telemetry & Audit Stream (/api/stats, /api/events)", False, str(e))

    # Summary Card
    print_header("VERIFICATION SUMMARY")
    if passed_count == total_checks:
        print(f" SUCCESS: All {passed_count}/{total_checks} verification checks passed cleanly!")
        print(" The MFA Physical Token Simulator & Dashboard are ready for demonstration.\n")
    else:
        print(f" WARNING: {passed_count}/{total_checks} checks passed. Inspect failures above.\n")


if __name__ == "__main__":
    main()
