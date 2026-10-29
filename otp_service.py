"""
OTP Service module for MFA Physical Token Simulator.
Handles cryptographically secure OTP generation, verification,
expiry checking, single-use invalidation, abuse prevention,
and aggregated security telemetry for the dashboard.
"""

from collections import deque
from datetime import datetime, timezone
import logging
import secrets
import threading
import time

logger = logging.getLogger("mfa_simulator")


class OTPServiceError(Exception):
    """Base exception for OTP service errors."""
    status_code = 400


class ValidationError(OTPServiceError):
    """Raised when OTP input is malformed or invalid."""
    status_code = 400


class NoActiveOTPError(OTPServiceError):
    """Raised when verification is attempted without an active OTP."""
    status_code = 400


class ExpiredOTPError(OTPServiceError):
    """Raised when OTP has expired."""
    status_code = 400


class InvalidOTPError(OTPServiceError):
    """Raised when submitted OTP does not match."""
    status_code = 400


class MaxAttemptsExceededError(OTPServiceError):
    """Raised when verification attempts exceed maximum allowed limit."""
    status_code = 400


class RateLimitError(OTPServiceError):
    """Raised when OTP generation request frequency exceeds rate limit."""
    status_code = 429


class OTPService:
    """
    In-memory, thread-safe OTP Manager simulating a hardware security token.

    Note for architecture:
    In-memory state is designed for single-process educational demonstrations.
    For multi-instance distributed deployments, this service should be backed
    by a shared store such as AWS ElastiCache / Redis or DynamoDB with TTL.
    """

    def __init__(self, ttl_seconds=120, rate_limit_seconds=5, max_attempts=5):
        self.default_ttl = ttl_seconds
        self.rate_limit_seconds = rate_limit_seconds
        self.max_attempts = max_attempts

        self._lock = threading.RLock()
        self._current_otp = None
        self._expires_at = 0.0
        self._created_at = 0.0
        self._failed_attempts = 0

        # Rate limiting: client_ip -> last_timestamp
        self._ip_generate_times = {}

        # Security audit event ring buffer (max 100 recent events)
        self._audit_events = deque(maxlen=100)

        # Recent verification/login attempts log (max 30)
        self._recent_attempts = deque(maxlen=30)

        # Cumulative system telemetry statistics
        self.stats = {
            "total_generated": 0,
            "total_verified": 0,
            "total_failed": 0,
            "total_expired": 0,
            "total_rate_limited": 0
        }

        # Hardware Token Metadata
        self.token_info = {
            "serial_number": "FOB-600-X7A-8892",
            "model": "SECURE-KEY FOB-600",
            "firmware": "v2.4.1-patch3 (Crypto-Core)",
            "algorithm": "CSPRNG (secrets) + HMAC-SHA256",
            "battery_level": "98%",
            "sync_drift": "+0.018s (Synchronized)",
            "lifecycle_status": "Active & Enrolled",
            "enrolled_to": "Demo Student Account",
            "last_synced": datetime.now(timezone.utc).isoformat()
        }

    def _record_audit_event(self, event_type, message, status="INFO", client_ip=None):
        """Records a sanitized security audit event without any secret values."""
        timestamp = datetime.now(timezone.utc).isoformat()
        event = {
            "timestamp": timestamp,
            "event_type": event_type,
            "message": message,
            "status": status,
            "client_ip": client_ip or "local"
        }
        self._audit_events.appendleft(event)

    def _record_attempt(self, client_ip, action, status, result_message):
        """Records a user/client authentication attempt for dashboard tracking."""
        timestamp = datetime.now(timezone.utc).isoformat()
        attempt = {
            "timestamp": timestamp,
            "client_ip": client_ip or "127.0.0.1",
            "action": action,
            "status": status,
            "details": result_message
        }
        self._recent_attempts.appendleft(attempt)

    def generate_otp(self, client_ip="127.0.0.1", ttl_seconds=None):
        """
        Generates a new cryptographically secure 6-digit OTP.

        Enforces rate limiting to prevent generation abuse.
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl

        with self._lock:
            now = time.time()

            # Check rate limiting
            last_request = self._ip_generate_times.get(client_ip, 0.0)
            elapsed = now - last_request
            if elapsed < self.rate_limit_seconds:
                wait_time = int(self.rate_limit_seconds - elapsed) + 1
                self.stats["total_rate_limited"] += 1
                logger.warning(
                    "Rate limit triggered for IP %s. Generation cooldown: %d seconds.",
                    client_ip, wait_time
                )
                self._record_audit_event(
                    "RATE_LIMIT_EXCEEDED",
                    f"OTP generation rate limit triggered. Cooldown: {wait_time}s.",
                    status="WARNING",
                    client_ip=client_ip
                )
                self._record_attempt(
                    client_ip, "OTP_GENERATE", "BLOCKED", f"Rate limit active ({wait_time}s cooldown)"
                )
                raise RateLimitError(
                    f"Please wait {wait_time} second(s) before generating a new OTP."
                )

            # Generate cryptographically secure 6-digit OTP (100000 to 999999)
            otp_val = f"{secrets.randbelow(900000) + 100000}"

            self._current_otp = otp_val
            self._created_at = now
            self._expires_at = now + ttl
            self._failed_attempts = 0
            self._ip_generate_times[client_ip] = now
            self.stats["total_generated"] += 1

            logger.info("New 6-digit OTP generated successfully. Expiry set to %d seconds.", ttl)
            self._record_audit_event(
                "OTP_GENERATED",
                f"Cryptographically secure 6-digit OTP generated. Validity: {ttl}s.",
                status="INFO",
                client_ip=client_ip
            )
            self._record_attempt(
                client_ip, "OTP_GENERATE", "SUCCESS", f"Token issued (TTL: {ttl}s)"
            )

            return {
                "otp": otp_val,
                "ttl_seconds": ttl,
                "expires_at": self._expires_at
            }

    def verify_otp(self, entered_otp, client_ip="127.0.0.1"):
        """
        Verifies the submitted OTP against the active OTP.

        Enforces:
        - Format validation (exact 6 numeric digits)
        - Active OTP check
        - Expiry check
        - Max attempt lockout
        - Single-use consumption (invalidated immediately on success)
        - Constant-time comparison
        """
        # Validate format
        if not isinstance(entered_otp, str):
            entered_otp = str(entered_otp or "")

        entered_clean = entered_otp.strip()

        if not entered_clean.isdigit() or len(entered_clean) != 6:
            self.stats["total_failed"] += 1
            logger.warning("OTP verification rejected: input format invalid.")
            self._record_audit_event(
                "VERIFY_MALFORMED_INPUT",
                "Verification rejected due to non-numeric or invalid length input.",
                status="WARNING",
                client_ip=client_ip
            )
            self._record_attempt(
                client_ip, "OTP_VERIFY", "REJECTED", "Malformed input format"
            )
            raise ValidationError("Invalid input. OTP must consist of exactly 6 numeric digits.")

        with self._lock:
            now = time.time()

            # Check if active OTP exists
            if self._current_otp is None:
                self.stats["total_failed"] += 1
                logger.warning("OTP verification attempted when no active OTP exists.")
                self._record_audit_event(
                    "VERIFY_NO_ACTIVE_OTP",
                    "Verification attempt rejected: No active OTP session found.",
                    status="WARNING",
                    client_ip=client_ip
                )
                self._record_attempt(
                    client_ip, "OTP_VERIFY", "FAILED", "No active token session"
                )
                raise NoActiveOTPError("No active OTP found. Please generate a new OTP first.")

            # Check expiration
            if now > self._expires_at:
                self._current_otp = None
                self._expires_at = 0.0
                self._failed_attempts = 0
                self.stats["total_expired"] += 1
                self.stats["total_failed"] += 1

                logger.warning("OTP verification failed: Token has expired.")
                self._record_audit_event(
                    "OTP_EXPIRED",
                    "Verification failed: Submitted token has expired and was discarded.",
                    status="WARNING",
                    client_ip=client_ip
                )
                self._record_attempt(
                    client_ip, "OTP_VERIFY", "EXPIRED", "Token expired past TTL"
                )
                raise ExpiredOTPError("OTP has expired. Please generate a new OTP.")

            # Check if max attempts previously reached
            if self._failed_attempts >= self.max_attempts:
                self._current_otp = None
                self._expires_at = 0.0
                self._failed_attempts = 0
                self.stats["total_failed"] += 1

                logger.warning("OTP invalidated: Maximum verification attempts exceeded.")
                self._record_audit_event(
                    "OTP_LOCKOUT_MAX_ATTEMPTS",
                    "Maximum verification attempts exceeded. Token invalidated.",
                    status="WARNING",
                    client_ip=client_ip
                )
                self._record_attempt(
                    client_ip, "OTP_VERIFY", "LOCKED", "Max attempts exceeded"
                )
                raise MaxAttemptsExceededError(
                    "Maximum verification attempts exceeded. OTP invalidated for security."
                )

            # Constant-time comparison to prevent timing side-channel attacks
            is_valid = secrets.compare_digest(entered_clean, self._current_otp)

            if is_valid:
                # SINGLE USE: Invalidate immediately upon successful verification
                self._current_otp = None
                self._expires_at = 0.0
                self._failed_attempts = 0
                self.stats["total_verified"] += 1

                logger.info("OTP verified successfully. Token consumed and invalidated.")
                self._record_audit_event(
                    "OTP_VERIFY_SUCCESS",
                    "OTP verified successfully. Token consumed and invalidated (single-use enforced).",
                    status="SUCCESS",
                    client_ip=client_ip
                )
                self._record_attempt(
                    client_ip, "OTP_VERIFY", "SUCCESS", "Authentication successful (Single-use token consumed)"
                )
                return {
                    "success": True,
                    "message": "OTP verified successfully! Token consumed."
                }
            else:
                # Increment failed attempts
                self._failed_attempts += 1
                self.stats["total_failed"] += 1
                remaining = self.max_attempts - self._failed_attempts

                if remaining <= 0:
                    # Invalidate token on reaching limit
                    self._current_otp = None
                    self._expires_at = 0.0
                    self._failed_attempts = 0

                    logger.warning(
                        "Incorrect OTP submitted. Max attempt limit reached (%d). Token invalidated.",
                        self.max_attempts
                    )
                    self._record_audit_event(
                        "OTP_LOCKOUT_MAX_ATTEMPTS",
                        f"Incorrect OTP submitted. Max attempts reached ({self.max_attempts}). Token invalidated.",
                        status="WARNING",
                        client_ip=client_ip
                    )
                    self._record_attempt(
                        client_ip, "OTP_VERIFY", "LOCKOUT", f"Max attempts ({self.max_attempts}) reached"
                    )
                    raise MaxAttemptsExceededError(
                        "Incorrect OTP. Maximum attempts exceeded; OTP has been invalidated."
                    )

                logger.warning(
                    "Incorrect OTP submitted. %d attempt(s) remaining.", remaining
                )
                self._record_audit_event(
                    "OTP_VERIFY_FAILED",
                    f"Incorrect OTP submitted. {remaining} attempt(s) remaining.",
                    status="WARNING",
                    client_ip=client_ip
                )
                self._record_attempt(
                    client_ip, "OTP_VERIFY", "INCORRECT", f"Wrong code ({remaining} tries left)"
                )
                raise InvalidOTPError(
                    f"Invalid OTP. {remaining} attempt(s) remaining."
                )

    def get_status(self):
        """
        Returns the non-sensitive status of the current OTP session.
        Never reveals the OTP value.
        """
        with self._lock:
            now = time.time()
            is_active = self._current_otp is not None and now <= self._expires_at
            remaining_seconds = max(0, int(self._expires_at - now)) if is_active else 0

            return {
                "has_active_otp": is_active,
                "remaining_seconds": remaining_seconds,
                "failed_attempts": self._failed_attempts,
                "max_attempts": self.max_attempts,
                "ttl_seconds": self.default_ttl
            }

    def get_stats(self):
        """
        Returns aggregated dashboard metrics, recent attempts,
        hardware token metadata, and success rate.
        """
        with self._lock:
            total_attempts = self.stats["total_verified"] + self.stats["total_failed"]
            success_rate = round(
                (self.stats["total_verified"] / total_attempts) * 100, 1
            ) if total_attempts > 0 else 100.0

            status = self.get_status()

            return {
                "metrics": {
                    "total_generated": self.stats["total_generated"],
                    "total_verified": self.stats["total_verified"],
                    "total_failed": self.stats["total_failed"],
                    "total_expired": self.stats["total_expired"],
                    "total_rate_limited": self.stats["total_rate_limited"],
                    "success_rate_pct": success_rate,
                    "total_attempts": total_attempts
                },
                "token_info": self.token_info.copy(),
                "session_status": status,
                "recent_attempts": list(self._recent_attempts)[:15]
            }

    def update_settings(self, ttl_seconds=None, rate_limit_seconds=None, max_attempts=None):
        """Updates operational parameters at runtime."""
        with self._lock:
            if ttl_seconds is not None:
                self.default_ttl = max(10, min(600, int(ttl_seconds)))
            if rate_limit_seconds is not None:
                self.rate_limit_seconds = max(0, min(60, int(rate_limit_seconds)))
            if max_attempts is not None:
                self.max_attempts = max(1, min(10, int(max_attempts)))

            self._record_audit_event(
                "CONFIG_UPDATED",
                f"Parameters updated: TTL={self.default_ttl}s, RateLimit={self.rate_limit_seconds}s, MaxAttempts={self.max_attempts}",
                status="INFO"
            )
            return {
                "ttl_seconds": self.default_ttl,
                "rate_limit_seconds": self.rate_limit_seconds,
                "max_attempts": self.max_attempts
            }

    def resync_token(self, client_ip="127.0.0.1"):
        """Simulates time synchronization of physical token drift."""
        with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            self.token_info["last_synced"] = now_iso
            self.token_info["sync_drift"] = "+0.004s (Calibrated)"
            self._record_audit_event(
                "TOKEN_RESYNCED",
                "Hardware token clock re-synchronized with NTP server.",
                status="SUCCESS",
                client_ip=client_ip
            )
            return {
                "success": True,
                "message": "Token clock re-synchronized successfully.",
                "last_synced": now_iso
            }

    def reset(self, client_ip="127.0.0.1"):
        """Resets the simulator session for new demonstration."""
        with self._lock:
            self._current_otp = None
            self._expires_at = 0.0
            self._created_at = 0.0
            self._failed_attempts = 0

            logger.info("Simulator session reset requested.")
            self._record_audit_event(
                "SIMULATOR_RESET",
                "Simulator session reset. Active tokens cleared.",
                status="INFO",
                client_ip=client_ip
            )
            self._record_attempt(
                client_ip, "RESET", "INFO", "Simulator session reset"
            )
            return {"success": True, "message": "Simulator session reset successfully."}

    def clear_audit_events(self, client_ip="127.0.0.1"):
        """Clears the in-memory audit logs and recent attempts buffer."""
        with self._lock:
            self._audit_events.clear()
            self._recent_attempts.clear()
            self._record_audit_event(
                "AUDIT_LOGS_CLEARED",
                "Audit logs cleared by administrator.",
                status="INFO",
                client_ip=client_ip
            )
            return {"success": True, "message": "Audit logs cleared."}

    def get_audit_events(self, limit=50):
        """Returns the recent security audit events list."""
        with self._lock:
            events = list(self._audit_events)
            return events[:limit]
