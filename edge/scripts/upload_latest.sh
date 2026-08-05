#!/usr/bin/env bash
# upload_latest.sh — Upload the latest (last) data point from a CSV file to DynamoDB.
#
# The CSV file contains rows of: timestamp,value
# e.g.  2026-08-04T04:00:07Z,0.7
#
# Only the last line (newest reading) is uploaded.
#
# Usage:
#   ./edge/scripts/upload_latest.sh /path/to/readings.csv
#
# Configuration (hardcoded for device 1, metric 5):
#   Device ID:  1
#   Metric ID:  5
#   Region:     us-east-2
#   Profile:    pichartprofile

set -euo pipefail

DEVICE_ID=1
METRIC_ID=5
REGION="us-east-2"
PROFILE="pichartprofile"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EDGE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PUT_DATAPOINT="$EDGE_DIR/src/put_datapoint.py"

# Resolve Python: prefer the edge venv, fall back to system python3
if [ -x "$EDGE_DIR/pienv/bin/python" ]; then
    PYTHON="$EDGE_DIR/pienv/bin/python"
else
    PYTHON="python3"
fi

# --- Validate arguments ---
if [ $# -lt 1 ]; then
    echo "Usage: $0 <csv-file>" >&2
    exit 1
fi

CSV_FILE="$1"

if [ ! -f "$CSV_FILE" ]; then
    echo "Error: File not found: $CSV_FILE" >&2
    exit 1
fi

# --- Read the last line ---
LAST_LINE="$(tail -n 1 "$CSV_FILE")"

if [ -z "$LAST_LINE" ]; then
    echo "Error: CSV file is empty: $CSV_FILE" >&2
    exit 1
fi

TIMESTAMP="$(echo "$LAST_LINE" | cut -d',' -f1)"
VALUE="$(echo "$LAST_LINE" | cut -d',' -f2)"

if [ -z "$TIMESTAMP" ] || [ -z "$VALUE" ]; then
    echo "Error: Could not parse timestamp and value from: $LAST_LINE" >&2
    exit 1
fi

# --- Upload ---
exec "$PYTHON" "$PUT_DATAPOINT" \
    --timestamp "$TIMESTAMP" \
    --value "$VALUE" \
    --device-id "$DEVICE_ID" \
    --metric-id "$METRIC_ID" \
    --region "$REGION" \
    --profile "$PROFILE"
