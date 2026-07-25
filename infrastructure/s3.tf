# ─────────────────────────────────────────────
# S3 Bucket for Chart Output
# ─────────────────────────────────────────────
# Stores:
#   output/{deviceID}/{metricID}/{year}/{month}/{metricID}-YYYYMMDD.png
#   output/file-list.json  — hierarchical index consumed by the frontend
#
# Public access is blocked by default. Static website hosting is enabled so
# the frontend can serve chart images and file-list.json via a bucket website
# endpoint or a CloudFront distribution placed in front of it.
# ─────────────────────────────────────────────

resource "aws_s3_bucket" "charts" {
  bucket = var.chart_bucket_name

  tags = merge(local.common_tags, {
    Component = "chart-storage"
  })
}

# Block all public access at the bucket ACL/policy level.
# Use the bucket policy below (or CloudFront OAC) to grant read access.
resource "aws_s3_bucket_public_access_block" "charts" {
  bucket = aws_s3_bucket.charts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable versioning so that file-list.json overwrites are recoverable.
resource "aws_s3_bucket_versioning" "charts" {
  bucket = aws_s3_bucket.charts.id

  versioning_configuration {
    status = "Disabled"
  }
}

# CORS configuration so the browser-based frontend can fetch chart images and
# file-list.json directly from the bucket without a proxy.
resource "aws_s3_bucket_cors_configuration" "charts" {
  bucket = aws_s3_bucket.charts.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = ["*"]      # Tighten to your frontend domain in production
    expose_headers  = ["ETag"]
    max_age_seconds = 3600
  }
}
