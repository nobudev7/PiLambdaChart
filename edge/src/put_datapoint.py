#!/usr/bin/env python3
"""
Standalone CLI to upload a single data point to AWS DynamoDB.

Reuses the existing DynamoDbUploader from the edge agent. Designed for
manual data injection, testing, or scripted one-shot uploads from edge
devices without running the full agent daemon.

USAGE
─────
  python edge/src/put_datapoint.py --timestamp "2026-08-04T20:30:00Z" --value 23.5 \
      --device-id 2 --metric-id 1

  # Use "now" for current UTC time
  python edge/src/put_datapoint.py --timestamp now --value 42.0 \
      --device-id 2 --metric-id 3

ARGUMENT RESOLUTION (Priority: CLI flag → Environment variable → Config file)
──────────────────
  --device-id     DEVICE_ID env       config.yaml device_id
  --region        AWS_REGION env      config.yaml aws.region        (default: us-east-1)
  --profile       AWS_PROFILE env     config.yaml aws.profile       (optional)
  --table         AWS_TELEMETRY_TABLE config.yaml aws.telemetry_table (default: IoT_Telemetry)
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import yaml

# Ensure the src directory is on the import path so uploaders can be found
# regardless of which directory the script is invoked from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from uploaders.dynamodb import DynamoDbUploader


def parse_timestamp(ts_str: str) -> datetime:
    """Parse a timestamp string into a UTC datetime object.

    Accepts:
      - "now"                        → current UTC time
      - "2026-08-04T20:30:00Z"      → ISO-8601 UTC
      - "2026-08-04T16:30:00-04:00" → ISO-8601 with offset (converted to UTC)
    """
    if ts_str.strip().lower() == "now":
        return datetime.now(timezone.utc)

    try:
        dt = datetime.fromisoformat(ts_str)
    except ValueError:
        raise ValueError(
            f"Invalid timestamp format: '{ts_str}'. "
            "Expected ISO-8601 (e.g. '2026-08-04T20:30:00Z') or 'now'."
        )

    # If naive (no timezone), assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        # Convert to UTC
        dt = dt.astimezone(timezone.utc)

    return dt


def load_config_file(config_path: str) -> dict:
    """Load config.yaml if it exists, returning an empty dict otherwise."""
    if config_path and os.path.exists(config_path):
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)
            return cfg if cfg else {}
    return {}


def resolve_args():
    """Parse CLI arguments and resolve values from CLI → env → config file."""
    parser = argparse.ArgumentParser(
        description="Upload a single data point to AWS DynamoDB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  python put_datapoint.py --timestamp "2026-08-04T20:30:00Z" --value 23.5 --device-id 2 --metric-id 1
  python put_datapoint.py --timestamp now --value 42.0 --device-id 2 --metric-id 3 --dry-run
  DEVICE_ID=2 python put_datapoint.py --timestamp now --value 18.7 --metric-id 1""",
    )

    parser.add_argument("--timestamp", required=True,
                        help="Timestamp: ISO-8601 (e.g. '2026-08-04T20:30:00Z') or 'now'.")
    parser.add_argument("--value", required=True, type=str,
                        help="Numeric value of the data point.")
    parser.add_argument("--device-id", type=int, default=None,
                        help="Device ID (int). Falls back to DEVICE_ID env or config.yaml.")
    parser.add_argument("--metric-id", type=int, required=True,
                        help="Metric ID (int).")
    parser.add_argument("--region", default=None,
                        help="AWS region. Falls back to AWS_REGION env or config.yaml. Default: us-east-1.")
    parser.add_argument("--profile", default=None,
                        help="AWS CLI profile name. Falls back to AWS_PROFILE env or config.yaml.")
    parser.add_argument("--table", default=None,
                        help="DynamoDB table name. Falls back to AWS_TELEMETRY_TABLE env or config.yaml. Default: IoT_Telemetry.")
    parser.add_argument("--config", default=None,
                        help="Path to config.yaml. Default: edge/config.yaml (if it exists).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Log the data point without uploading to DynamoDB.")

    args = parser.parse_args()

    # Determine config file path
    if args.config is None:
        # Look for config.yaml relative to this script's parent directory (edge/)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        default_config = os.path.join(script_dir, "..", "config.yaml")
        if os.path.exists(default_config):
            args.config = default_config

    cfg = load_config_file(args.config)
    aws_cfg = cfg.get("aws", {})

    # Resolve device_id: CLI → env → config
    if args.device_id is None:
        env_device = os.environ.get("DEVICE_ID")
        if env_device:
            try:
                args.device_id = int(env_device)
            except ValueError:
                print(f"Error: Invalid DEVICE_ID environment variable: '{env_device}'", file=sys.stderr)
                sys.exit(1)
        elif "device_id" in cfg:
            args.device_id = int(cfg["device_id"])
        else:
            print("Error: --device-id is required (or set DEVICE_ID env / device_id in config.yaml).", file=sys.stderr)
            sys.exit(1)

    # Resolve region: CLI → env → config → default
    if args.region is None:
        args.region = os.environ.get("AWS_REGION") or aws_cfg.get("region") or "us-east-1"

    # Resolve profile: CLI → env → config
    if args.profile is None:
        args.profile = (
            os.environ.get("AWS_PROFILE")
            or os.environ.get("AWS_DEFAULT_PROFILE")
            or aws_cfg.get("profile")
        )

    # Resolve table: CLI → env → config → default
    if args.table is None:
        args.table = os.environ.get("AWS_TELEMETRY_TABLE") or aws_cfg.get("telemetry_table") or "IoT_Telemetry"

    # Resolve dry-run: CLI flag or config aws.enabled == false
    if not args.dry_run:
        enabled = aws_cfg.get("enabled")
        if enabled is not None and not enabled:
            args.dry_run = True

    return args


def main():
    args = resolve_args()

    # Parse and validate timestamp
    try:
        timestamp = parse_timestamp(args.timestamp)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate value
    try:
        value = Decimal(args.value)
    except InvalidOperation:
        print(f"Error: Invalid numeric value: '{args.value}'", file=sys.stderr)
        sys.exit(1)

    # Set up uploader
    uploader = DynamoDbUploader(
        region=args.region,
        table_name=args.table,
        enabled=not args.dry_run,
        profile=args.profile,
    )

    try:
        uploader.setup()
    except Exception as e:
        print(f"Error: Failed to connect to DynamoDB: {e}", file=sys.stderr)
        sys.exit(1)

    # Build data point
    data_point = {
        "device_id": args.device_id,
        "metric_id": args.metric_id,
        "value": float(value),
        "timestamp": timestamp,
    }

    # Upload (synchronous, one-shot)
    success = uploader._put_item_sync(data_point)

    # Format output
    utc_year = timestamp.strftime("%Y")
    pk = f"{args.device_id}#{args.metric_id}#{utc_year}"
    sk = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

    if args.dry_run:
        print(f"[DRY-RUN] OK {pk} {sk} {value}")
    elif success:
        print(f"OK {pk} {sk} {value}")
    else:
        print(f"Error: Failed to upload data point.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
