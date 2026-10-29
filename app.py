"""
MFA Physical Token Simulator - Main Flask Application.
Demonstrates cryptographically secure OTP generation, verification,
rate limiting, security event logging, dashboard analytics, and AWS CloudWatch integration.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from config import Config
from cloudwatch_logger import setup_logging, get_cloudwatch_status
from otp_service import (
    OTPService,
    OTPServiceError,
    ValidationError,
    NoActiveOTPError,
    ExpiredOTPError,
    InvalidOTPError,
    MaxAttemptsExceededError,
    RateLimitError
)

BASE_DIR = Path(__file__).resolve().parent


def get_client_ip():
    """Extracts client IP address safely, respecting reverse proxy headers."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


def create_app(config_class=Config):
    """
    Application factory pattern to configure and return the Flask application.
    """
    app = Flask(__name__, static_folder=None)
    app.config.from_object(config_class)

    # Initialize Logger (Local console, local file, and optional AWS CloudWatch)
    logger, cw_state = setup_logging(app.config)
    app.logger_instance = logger
    app.cloudwatch_state = cw_state

    # Initialize OTP Service with configured limits
    otp_service = OTPService(
        ttl_seconds=app.config.get("OTP_TTL_SECONDS", 120),
        rate_limit_seconds=app.config.get("RATE_LIMIT_GENERATE_SECONDS", 5),
        max_attempts=app.config.get("MAX_VERIFY_ATTEMPTS", 5)
    )
    app.otp_service = otp_service

    # ==========================================================
    # Frontend Routes
    # ==========================================================

    @app.get("/")
    def index():
        """Serves the primary MFA Simulator dashboard HTML."""
        return send_from_directory(BASE_DIR, "index.html")

    @app.get("/style.css")
    def stylesheet():
        """Serves the application CSS stylesheet."""
        return send_from_directory(BASE_DIR, "style.css", mimetype="text/css")

    @app.get("/script.js")
    def javascript():
        """Serves the application JavaScript file."""
        return send_from_directory(BASE_DIR, "script.js", mimetype="application/javascript")

    # ==========================================================
    # API Endpoints
    # ==========================================================

    @app.post("/api/generate")
    def generate_otp():
        """
        Generates a new cryptographically secure 6-digit OTP.

        Enforces rate limiting. Returns the OTP in the JSON response
        only when DEMO_SHOW_OTP is True (educational demo mode).
        """
        client_ip = get_client_ip()

        try:
            result = otp_service.generate_otp(
                client_ip=client_ip,
                ttl_seconds=app.config.get("OTP_TTL_SECONDS", 120)
            )

            response_data = {
                "success": True,
                "message": f"OTP generated successfully. Valid for {result['ttl_seconds']} seconds.",
                "ttl_seconds": result["ttl_seconds"],
                "expires_at": result["expires_at"],
                "demo_mode": app.config.get("DEMO_SHOW_OTP", True)
            }

            # In demo mode, expose the simulated hardware token display value
            if app.config.get("DEMO_SHOW_OTP", True):
                response_data["otp"] = result["otp"]
            else:
                response_data["otp"] = None
                response_data["message"] = (
                    "OTP generated securely. In non-demo mode, OTP is delivered "
                    "via out-of-band channel or generated on-device."
                )

            return jsonify(response_data), 200

        except RateLimitError as rate_err:
            return jsonify({
                "success": False,
                "error": "RATE_LIMIT_EXCEEDED",
                "message": str(rate_err)
            }), 429
        except Exception as exc:
            logger.error("Unexpected error during OTP generation: %s", exc, exc_info=True)
            return jsonify({
                "success": False,
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred while generating the OTP."
            }), 500

    @app.post("/api/verify")
    def verify_otp():
        """
        Accepts a 6-digit OTP and verifies it against the active session.

        Enforces:
        - 6-digit numeric input validation
        - Active session existence
        - Expiry checking
        - Single-use consumption (invalidated immediately on success)
        - Brute-force attempt lockout
        """
        client_ip = get_client_ip()

        # Handle malformed or missing JSON body gracefully
        if not request.is_json:
            data = request.get_json(silent=True)
            if data is None:
                logger.warning("Verify request rejected: Missing or invalid JSON body from %s", client_ip)
                return jsonify({
                    "success": False,
                    "error": "INVALID_JSON",
                    "message": "Request body must be valid JSON containing an 'otp' key."
                }), 400
        else:
            data = request.get_json()

        if not data or "otp" not in data:
            logger.warning("Verify request rejected: 'otp' parameter missing from %s", client_ip)
            return jsonify({
                "success": False,
                "error": "MISSING_FIELD",
                "message": "Missing required field 'otp'."
            }), 400

        entered_otp = data.get("otp")

        try:
            result = otp_service.verify_otp(entered_otp, client_ip=client_ip)
            return jsonify(result), 200

        except ValidationError as val_err:
            return jsonify({
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": str(val_err)
            }), 400
        except NoActiveOTPError as no_otp_err:
            return jsonify({
                "success": False,
                "error": "NO_ACTIVE_OTP",
                "message": str(no_otp_err)
            }), 400
        except ExpiredOTPError as exp_err:
            return jsonify({
                "success": False,
                "error": "OTP_EXPIRED",
                "message": str(exp_err)
            }), 400
        except MaxAttemptsExceededError as max_err:
            return jsonify({
                "success": False,
                "error": "MAX_ATTEMPTS_EXCEEDED",
                "message": str(max_err)
            }), 400
        except InvalidOTPError as inv_err:
            return jsonify({
                "success": False,
                "error": "INVALID_OTP",
                "message": str(inv_err)
            }), 400
        except Exception as exc:
            logger.error("Unexpected error during OTP verification: %s", exc, exc_info=True)
            return jsonify({
                "success": False,
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred while verifying the OTP."
            }), 500

    @app.get("/api/health")
    def health_check():
        """
        Health-check endpoint. Provides system status, CloudWatch logging state,
        and operational parameters without revealing secrets or internal paths.
        """
        cw_status = get_cloudwatch_status()
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cloudwatch": {
                "enabled": cw_status.get("enabled", False),
                "status": cw_status.get("status", "unknown"),
                "log_group": cw_status.get("log_group"),
                "region": cw_status.get("region"),
                "message": cw_status.get("message")
            },
            "demo_mode": app.config.get("DEMO_SHOW_OTP", True),
            "otp_ttl_seconds": app.config.get("OTP_TTL_SECONDS", 120),
            "rate_limit_seconds": app.config.get("RATE_LIMIT_GENERATE_SECONDS", 5),
            "max_attempts": app.config.get("MAX_VERIFY_ATTEMPTS", 5)
        }), 200

    @app.get("/api/status")
    def token_status():
        """
        Returns real-time non-sensitive token state for frontend synchronization.
        """
        status_info = otp_service.get_status()
        status_info["cloudwatch"] = get_cloudwatch_status()
        return jsonify(status_info), 200

    @app.get("/api/stats")
    def dashboard_stats():
        """
        Returns aggregated metrics, hardware token metadata,
        recent attempts, and CloudWatch state for the main dashboard view.
        """
        data = otp_service.get_stats()
        data["cloudwatch"] = get_cloudwatch_status()
        return jsonify({
            "success": True,
            "data": data
        }), 200

    @app.get("/api/events")
    def security_events():
        """
        Returns recent security audit events for real-time dashboard display.
        """
        limit = request.args.get("limit", 50, type=int)
        events = otp_service.get_audit_events(limit=limit)
        return jsonify({
            "success": True,
            "count": len(events),
            "events": events
        }), 200

    @app.get("/api/settings")
    def get_settings():
        """Returns current operational settings."""
        return jsonify({
            "success": True,
            "settings": {
                "otp_ttl_seconds": app.config.get("OTP_TTL_SECONDS", 120),
                "demo_show_otp": app.config.get("DEMO_SHOW_OTP", True),
                "rate_limit_seconds": app.config.get("RATE_LIMIT_GENERATE_SECONDS", 5),
                "max_attempts": app.config.get("MAX_VERIFY_ATTEMPTS", 5),
                "cloudwatch_enabled": app.config.get("CLOUDWATCH_ENABLED", False),
                "cloudwatch_log_group": app.config.get("CLOUDWATCH_LOG_GROUP", "/aws/flask/MFA-Token-Simulator"),
                "aws_default_region": app.config.get("AWS_DEFAULT_REGION", "ap-southeast-2")
            }
        }), 200

    @app.post("/api/settings")
    def update_settings():
        """Updates operational settings at runtime."""
        data = request.get_json(silent=True) or {}

        if "otp_ttl_seconds" in data:
            val = int(data["otp_ttl_seconds"])
            app.config["OTP_TTL_SECONDS"] = val
            otp_service.update_settings(ttl_seconds=val)

        if "demo_show_otp" in data:
            app.config["DEMO_SHOW_OTP"] = bool(data["demo_show_otp"])

        if "rate_limit_seconds" in data:
            val = int(data["rate_limit_seconds"])
            app.config["RATE_LIMIT_GENERATE_SECONDS"] = val
            otp_service.update_settings(rate_limit_seconds=val)

        if "max_attempts" in data:
            val = int(data["max_attempts"])
            app.config["MAX_VERIFY_ATTEMPTS"] = val
            otp_service.update_settings(max_attempts=val)

        return jsonify({
            "success": True,
            "message": "Settings updated successfully."
        }), 200

    @app.post("/api/token/resync")
    def resync_hardware_token():
        """Simulates clock calibration and synchronization of the hardware token."""
        client_ip = get_client_ip()
        result = otp_service.resync_token(client_ip=client_ip)
        return jsonify(result), 200

    @app.post("/api/logs/clear")
    def clear_audit_logs():
        """Clears in-memory audit logs and recent attempt history."""
        client_ip = get_client_ip()
        result = otp_service.clear_audit_events(client_ip=client_ip)
        return jsonify(result), 200

    @app.post("/api/reset")
    def reset_session():
        """
        Resets active token and attempt counters for demonstration purposes.
        """
        client_ip = get_client_ip()
        result = otp_service.reset(client_ip=client_ip)
        return jsonify(result), 200

    # ==========================================================
    # Global Error Handlers (JSON API responses)
    # ==========================================================

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return jsonify({
                "success": False,
                "error": "NOT_FOUND",
                "message": "The requested API endpoint was not found."
            }), 404
        return send_from_directory(BASE_DIR, "index.html")

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            "success": False,
            "error": "METHOD_NOT_ALLOWED",
            "message": f"Method {request.method} is not allowed for this route."
        }), 405

    @app.errorhandler(500)
    def internal_error(error):
        logger.error("Internal Server Error: %s", error, exc_info=True)
        return jsonify({
            "success": False,
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An internal server error occurred."
        }), 500

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        return jsonify({
            "success": False,
            "error": error.name.upper().replace(" ", "_"),
            "message": error.description
        }), error.code

    return app


# Default application instance for WSGI / local execution
app = create_app()

if __name__ == "__main__":
    debug_mode = app.config.get("DEBUG", False)
    port = int(os.getenv("PORT", "5000"))
    app.logger_instance.info("Starting MFA Token Simulator on port %d (Debug: %s)", port, debug_mode)
    app.run(host="127.0.0.1", port=port, debug=debug_mode)
