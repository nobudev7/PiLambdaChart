#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# deploy.sh — Deploy PiLambdaChart frontend to S3 static website hosting
# ═══════════════════════════════════════════════════════════════════════════
#
# USAGE
#   ./deploy.sh [options]
#
# OPTIONS
#   -b, --bucket  <name>   S3 bucket name (required, or set S3_BUCKET env var)
#   -p, --profile <name>   AWS CLI profile (default: default)
#   -r, --region  <name>   AWS region      (default: us-east-1)
#   --cloudfront  <id>     CloudFront distribution ID to invalidate after deploy
#   --include-output       Upload PNG and JSON chart files from frontend/public/output
#   --dry-run              Print what would be uploaded without actually uploading
#   -h, --help             Show this help
#
# EXAMPLES
#   # Basic deploy (frontend static assets only)
#   ./deploy.sh --bucket pilambdachart-charts
#
#   # Deploy frontend static assets AND local output chart files
#   ./deploy.sh --bucket pilambdachart-charts --include-output
#
#   # With CloudFront invalidation
#   ./deploy.sh --bucket pilambdachart-charts --cloudfront E1ABCDEF123456
#
# WHAT IT DOES
#   1. Syncs frontend/public/ static website files (CSS, JS, index.html) to S3
#   2. Optionally syncs frontend/public/output chart PNGs, JSONs, and file-list.json when --include-output is set
#   3. Optionally creates a CloudFront invalidation to flush CDN edge caches
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Defaults ────────────────────────────────────────────────────────────────
BUCKET="${S3_BUCKET:-}"
PROFILE="${AWS_PROFILE:-default}"
REGION="${AWS_REGION:-us-east-1}"
CF_DIST_ID="${CF_DIST_ID:-}"
DRY_RUN=false
INCLUDE_OUTPUT=false

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUBLIC_DIR="$SCRIPT_DIR/public"

# ── Argument parsing ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    -b|--bucket)         BUCKET="$2";         shift 2 ;;
    -p|--profile)        PROFILE="$2";        shift 2 ;;
    -r|--region)         REGION="$2";         shift 2 ;;
    --cloudfront)        CF_DIST_ID="$2";      shift 2 ;;
    --include-output)     INCLUDE_OUTPUT=true; shift ;;
    --dry-run)           DRY_RUN=true;        shift   ;;
    -h|--help)
      sed -n '/^# USAGE/,/^set -/p' "$0" | grep '^#' | sed 's/^# \?//'
      exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

# ── Validation ───────────────────────────────────────────────────────────────
if [[ -z "$BUCKET" ]]; then
  echo "Error: S3 bucket name is required. Use --bucket <name> or set S3_BUCKET." >&2
  exit 1
fi

if ! command -v aws &>/dev/null; then
  echo "Error: AWS CLI not found. Install it from https://aws.amazon.com/cli/" >&2
  exit 1
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              PiLambdaChart — S3 Static Site Deploy             ║"
echo "╠════════════════════════════════════════════════════════════════╣"
printf "║  Source   : %-51s║\n" "$PUBLIC_DIR"
printf "║  Bucket   : s3://%-46s║\n" "$BUCKET"
printf "║  Profile  : %-51s║\n" "$PROFILE"
printf "║  Region   : %-51s║\n" "$REGION"
printf "║  Out Data : %-51s║\n" "$([ "$INCLUDE_OUTPUT" == true ] && echo 'Enabled (--include-output)' || echo 'Skipped (pass --include-output to upload)')"
[[ -n "$CF_DIST_ID" ]] && printf "║  CloudFront: %-50s║\n" "$CF_DIST_ID"
[[ "$DRY_RUN" == true ]] && printf "║  %-66s║\n" "⚠ DRY RUN — no files will be uploaded"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

AWS_CMD=(aws --profile "$PROFILE" --region "$REGION")
DRY=""
if [[ "$DRY_RUN" == true ]]; then
  DRY="--dryrun"
fi

# ── Step 1: Upload static assets (JS, CSS) — long cache ─────────────────────
echo "▶ Uploading static CSS assets — cache 1 year…"
"${AWS_CMD[@]}" s3 sync "$PUBLIC_DIR" "s3://$BUCKET" \
  ${DRY:+"$DRY"} \
  --exclude "*" \
  --include "*.css" \
  --cache-control "public, max-age=31536000, immutable" \
  --content-type "text/css"

echo "▶ Uploading static JS assets — cache 1 year…"
"${AWS_CMD[@]}" s3 sync "$PUBLIC_DIR" "s3://$BUCKET" \
  ${DRY:+"$DRY"} \
  --exclude "*" \
  --include "*.js" \
  --cache-control "public, max-age=31536000, immutable" \
  --content-type "application/javascript"

# ── Step 2: Upload chart PNGs and JSON sidecars (optional) ─────────────────
if [[ "$INCLUDE_OUTPUT" == true ]]; then
  echo "▶ Uploading chart PNGs — cache 1 hour…"
  "${AWS_CMD[@]}" s3 sync "$PUBLIC_DIR/output" "s3://$BUCKET/output" \
    ${DRY:+"$DRY"} \
    --exclude "*" \
    --include "*.png" \
    --cache-control "public, max-age=3600" \
    --content-type "image/png"

  echo "▶ Uploading chart data JSON sidecars — cache 1 hour…"
  "${AWS_CMD[@]}" s3 sync "$PUBLIC_DIR/output" "s3://$BUCKET/output" \
    ${DRY:+"$DRY"} \
    --exclude "*" \
    --exclude "file-list.json" \
    --include "*.json" \
    --cache-control "public, max-age=3600" \
    --content-type "application/json"

  # ── Step 3: Upload file-list.json & metadata.json ─────────────────────────
  echo "▶ Uploading file-list.json — cache 60 seconds…"
  if [[ -f "$PUBLIC_DIR/output/file-list.json" ]]; then
    "${AWS_CMD[@]}" s3 cp "$PUBLIC_DIR/output/file-list.json" \
      "s3://$BUCKET/output/file-list.json" \
      ${DRY:+"$DRY"} \
      --cache-control "public, max-age=60" \
      --content-type "application/json"
  else
    echo "  (no file-list.json found locally — skipped)"
  fi

  echo "▶ Uploading metadata.json — cache 60 seconds…"
  if [[ -f "$PUBLIC_DIR/output/metadata.json" ]]; then
    "${AWS_CMD[@]}" s3 cp "$PUBLIC_DIR/output/metadata.json" \
      "s3://$BUCKET/output/metadata.json" \
      ${DRY:+"$DRY"} \
      --cache-control "public, max-age=60" \
      --content-type "application/json"
  else
    echo "  (no metadata.json found locally — skipped)"
  fi
else
  echo "▶ Skipping output folder chart assets upload (pass --include-output to enable)"
fi

# ── Step 4: Upload index.html — no cache (always fetch latest) ───────────────
echo "▶ Uploading index.html — no cache…"
"${AWS_CMD[@]}" s3 cp "$PUBLIC_DIR/index.html" "s3://$BUCKET/index.html" \
  ${DRY:+"$DRY"} \
  --cache-control "no-cache, no-store, must-revalidate" \
  --content-type "text/html; charset=utf-8"

# ── Step 5: CloudFront invalidation ──────────────────────────────────────────
if [[ -n "$CF_DIST_ID" && "$DRY_RUN" == false ]]; then
  echo "▶ Creating CloudFront invalidation for /*…"
  INVALIDATION_ID=$("${AWS_CMD[@]}" cloudfront create-invalidation \
    --distribution-id "$CF_DIST_ID" \
    --paths "/*" \
    --query 'Invalidation.Id' \
    --output text)
  echo "  Invalidation created: $INVALIDATION_ID"
  echo "  (CDN edges will refresh within ~60 seconds)"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "✓ Deploy complete."
if [[ "$DRY_RUN" == false ]]; then
  if [[ -n "$CF_DIST_ID" ]]; then
    echo "  CloudFront:  https://$(
      "${AWS_CMD[@]}" cloudfront get-distribution \
        --id "$CF_DIST_ID" \
        --query 'Distribution.DomainName' \
        --output text 2>/dev/null || echo 'your-cloudfront-domain.cloudfront.net'
    )"
  fi
fi
