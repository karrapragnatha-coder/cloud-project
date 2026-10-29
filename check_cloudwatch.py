"""
AWS CloudWatch Diagnostics Helper for MFA Token Simulator.
Verifies whether AWS credentials are configured, tests connectivity to region ap-southeast-2,
and checks CloudWatch log group access without crashing.

Usage:
    python check_cloudwatch.py
"""

import os
import sys

# Configure stdout safely for Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main():
    print("\n" + "=" * 65)
    print(" AWS CLOUDWATCH LOGS CONNECTIVITY CHECK")
    print("=" * 65)

    from config import Config
    region = Config.AWS_DEFAULT_REGION
    log_group = Config.CLOUDWATCH_LOG_GROUP
    cw_enabled = Config.CLOUDWATCH_ENABLED

    print(f" Target Region:    {region}")
    print(f" Target Log Group: {log_group}")
    print(f" Config Enabled:   {cw_enabled}")
    print("-" * 65)

    try:
        import boto3
        from botocore.exceptions import NoCredentialsError, ClientError

        session = boto3.Session()
        credentials = session.get_credentials()

        if credentials is None:
            print(" [STATUS] AWS Credentials: NOT FOUND")
            print(" [INFO]   Application is running in LOCAL LOGGING mode (default).")
            print(" [INFO]   Local logs are written to: logs/mfa_simulator.log")
            print("\n To enable AWS CloudWatch logging in the future:")
            print("   1. Run: aws configure")
            print("   2. Set: CLOUDWATCH_ENABLED=1 in your .env file")
            print("   3. Restart: python app.py\n")
            return

        print(" [STATUS] AWS Credentials: FOUND (Standard Credential Provider Chain)")
        client = boto3.client("logs", region_name=region)

        # Check if we can describe log groups
        response = client.describe_log_groups(logGroupNamePrefix=log_group, limit=5)
        groups = [g["logGroupName"] for g in response.get("logGroups", [])]

        if log_group in groups:
            print(f" [PASS]   Log Group exists: {log_group}")
        else:
            print(f" [INFO]   Log Group does not exist yet. Watchtower will create it on startup.")

        print(f" [SUCCESS] AWS CloudWatch connection verified for region {region}!\n")

    except Exception as e:
        print(f" [WARNING] AWS Check returned: {e}")
        print(" [INFO]    Flask will continue smoothly using local console & file logging.\n")


if __name__ == "__main__":
    main()

