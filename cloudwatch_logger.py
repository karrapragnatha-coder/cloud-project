"""
Logging module for MFA Physical Token Simulator.
Provides local console logging, optional local rotating file logging,
and optional AWS CloudWatch Logs integration using watchtower and boto3.
"""

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

# Module-level variable tracking current CloudWatch integration state
_cloudwatch_state = {
    "enabled": False,
    "status": "disabled",
    "message": "CloudWatch integration is disabled by default.",
    "log_group": None,
    "log_stream": None,
    "region": None,
    "error": None
}

LOGGER_NAME = "mfa_simulator"


def setup_logging(config=None):
    """
    Configures and returns the application logger.

    Args:
        config: Config object or class with logging and AWS settings.

    Returns:
        tuple: (logger, cloudwatch_state_dict)
    """
    global _cloudwatch_state

    # Fallback default values if config is None
    log_level_name = getattr(config, "LOG_LEVEL", "INFO") if config else "INFO"
    log_level = getattr(logging, log_level_name, logging.INFO)
    log_file_path = getattr(config, "LOG_FILE_PATH", "logs/mfa_simulator.log") if config else "logs/mfa_simulator.log"
    cw_enabled = getattr(config, "CLOUDWATCH_ENABLED", False) if config else False
    cw_log_group = getattr(config, "CLOUDWATCH_LOG_GROUP", "/aws/flask/MFA-Token-Simulator") if config else "/aws/flask/MFA-Token-Simulator"
    cw_log_stream = getattr(config, "CLOUDWATCH_LOG_STREAM", "simulator-flask-stream") if config else "simulator-flask-stream"
    aws_region = getattr(config, "AWS_DEFAULT_REGION", "ap-southeast-2") if config else "ap-southeast-2"

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(log_level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if logger.handlers:
        logger.handlers.clear()

    # Formatter for console and file
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Console / Terminal Handler (always enabled)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. Local Rotating File Handler (optional, fails gracefully if filesystem restricted)
    try:
        file_path = Path(log_file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=str(file_path),
            maxBytes=2 * 1024 * 1024,  # 2 MB per file
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as file_err:
        logger.warning("Could not initialize local file log handler: %s", file_err)

    # 3. AWS CloudWatch Handler (Optional)
    if not cw_enabled:
        _cloudwatch_state = {
            "enabled": False,
            "status": "disabled",
            "message": "AWS CloudWatch logging is disabled by configuration (Local logging only).",
            "log_group": cw_log_group,
            "log_stream": cw_log_stream,
            "region": aws_region,
            "error": None
        }
        logger.info("Local logging active. CloudWatch logging disabled.")
    else:
        logger.info("Attempting to initialize AWS CloudWatch logging in region %s...", aws_region)
        try:
            import boto3
            import watchtower

            # Create boto3 CloudWatch Logs client using AWS credential provider chain
            cw_client = boto3.client("logs", region_name=aws_region)

            cw_handler = watchtower.CloudWatchLogHandler(
                log_group_name=cw_log_group,
                log_stream_name=cw_log_stream,
                boto3_client=cw_client,
                send_interval=5,
                create_log_group=True,
                create_log_stream=True
            )
            cw_handler.setLevel(log_level)
            cw_handler.setFormatter(formatter)
            logger.addHandler(cw_handler)

            _cloudwatch_state = {
                "enabled": True,
                "status": "connected",
                "message": f"Connected to AWS CloudWatch log group '{cw_log_group}'.",
                "log_group": cw_log_group,
                "log_stream": cw_log_stream,
                "region": aws_region,
                "error": None
            }
            logger.info("AWS CloudWatch logging initialized successfully on group: %s", cw_log_group)
        except Exception as aws_err:
            error_msg = str(aws_err)
            _cloudwatch_state = {
                "enabled": False,
                "status": "failed",
                "message": "AWS CloudWatch initialization failed. Fallback to local logging active.",
                "log_group": cw_log_group,
                "log_stream": cw_log_stream,
                "region": aws_region,
                "error": error_msg
            }
            logger.warning(
                "AWS CloudWatch initialization failed: %s. Local logging will continue normally.",
                error_msg
            )

    return logger, _cloudwatch_state


def get_cloudwatch_status():
    """Returns the current CloudWatch connection status dictionary."""
    return _cloudwatch_state.copy()

