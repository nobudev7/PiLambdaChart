# ─────────────────────────────────────────────
# CloudFront CDN Distribution with Origin Access Control (OAC)
# and HTTP Basic Authentication
# ─────────────────────────────────────────────
#
# This file provisions:
#   1. CloudFront Origin Access Control (OAC) — grants secure private S3 access.
#   2. CloudFront Function — enforces HTTP Basic Auth (enabled by default when CloudFront is active).
#   3. CloudFront Distribution — edge caching for chart assets, index.html, and file-list.json.
#   4. S3 Bucket Policy — allows CloudFront OAC to read objects from private chart bucket.
#
# Controlled by variables:
#   - enable_cloudfront (default: false — set to true to deploy)
#   - enable_cloudfront_basic_auth (default: true — active when enable_cloudfront = true)
#   - basic_auth_username (default: "admin")
#   - basic_auth_password (default: "pilambdachart2026!")
#   - custom_domain_name / acm_certificate_arn (optional CNAME setup)
# ─────────────────────────────────────────────

# 1. Origin Access Control (OAC) for private S3 integration
resource "aws_cloudfront_origin_access_control" "s3_oac" {
  count                             = var.enable_cloudfront ? 1 : 0
  name                              = "${var.project_name}-s3-oac"
  description                       = "OAC for ${var.chart_bucket_name} S3 bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# 2. CloudFront Function for HTTP Basic Authentication with Cookie Persistence
#
# On first visit (no cookie): prompts HTTP Basic Auth.
# On successful auth: sets a '__plc_auth' cookie valid for 30 days.
# On return visits: validates the cookie — no re-prompt needed.
# This solves iOS Safari aggressively dropping Basic Auth credentials.
resource "aws_cloudfront_function" "basic_auth" {
  count   = var.enable_cloudfront && var.enable_cloudfront_basic_auth ? 1 : 0
  name    = "${var.project_name}-basic-auth"
  runtime = "cloudfront-js-2.0"
  comment = "HTTP Basic Auth with 30-day cookie persistence for ${var.project_name}"
  publish = true

  code = <<EOF
var AUTH_STRING = "Basic ${base64encode("${var.basic_auth_username}:${var.basic_auth_password}")}";
var COOKIE_NAME = "__plc_auth";
var COOKIE_MAX_AGE = 2592000; // 30 days in seconds
var REDIRECT_FLAG = "__plc_r";

// Simple hash of the password to use as the cookie token.
// Not cryptographic, but sufficient for a private dashboard —
// an attacker would need the password to forge the cookie value.
function computeToken(s) {
    var h = 0;
    for (var i = 0; i < s.length; i++) {
        h = ((h << 5) - h + s.charCodeAt(i)) | 0;
    }
    return "plc" + (h >>> 0).toString(36);
}

var VALID_TOKEN = computeToken("${var.basic_auth_password}");

function handler(event) {
    var request = event.request;
    var headers = request.headers;

    // 1. Check for valid auth cookie (using native request.cookies in runtime 2.0)
    if (request.cookies && request.cookies[COOKIE_NAME] && request.cookies[COOKIE_NAME].value === VALID_TOKEN) {
        return request; // Cookie valid — pass through
    }

    // 2. Prevent infinite redirect loops (e.g. if cookies are blocked by the browser)
    if (request.querystring && request.querystring[REDIRECT_FLAG]) {
        return request; // Already tried redirecting once, fallback to normal auth pass-through
    }

    // 3. Check Basic Auth header
    if (headers.authorization && headers.authorization.value === AUTH_STRING) {
        // Build redirect URI preserving other query parameters, adding the redirect flag
        var redirectUri = request.uri;
        var qs = [];
        if (request.querystring) {
            for (var key in request.querystring) {
                if (key !== REDIRECT_FLAG) {
                    qs.push(key + "=" + request.querystring[key].value);
                }
            }
        }
        qs.push(REDIRECT_FLAG + "=1");
        redirectUri += "?" + qs.join("&");

        return {
            statusCode: 302,
            statusDescription: "Found",
            headers: {
                "location": { value: redirectUri },
                "cache-control": { value: "no-cache, no-store" }
            },
            cookies: {
                "__plc_auth": {
                    value: VALID_TOKEN,
                    attributes: "Path=/; Max-Age=" + COOKIE_MAX_AGE + "; Secure; HttpOnly; SameSite=Lax"
                }
            }
        };
    }

    // 4. No cookie, no auth — prompt
    return {
        statusCode: 401,
        statusDescription: "Unauthorized",
        headers: {
            "www-authenticate": { value: 'Basic realm="PiLambdaChart Dashboard", charset="UTF-8"' }
        }
    };
}
EOF
}

# Managed Cache Policy data source for S3 origin (Managed-CachingOptimized)
data "aws_cloudfront_cache_policy" "caching_optimized" {
  name = "Managed-CachingOptimized"
}

# 3. CloudFront Distribution
resource "aws_cloudfront_distribution" "s3_distribution" {
  count = var.enable_cloudfront ? 1 : 0

  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${var.project_name} S3 Dashboard CDN Distribution"
  default_root_object = "index.html"
  web_acl_id          = var.web_acl_id != "" ? var.web_acl_id : null

  aliases = var.custom_domain_name != "" ? [var.custom_domain_name] : []

  origin {
    domain_name              = aws_s3_bucket.charts.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.s3_oac[0].id
    origin_id                = "S3-${aws_s3_bucket.charts.id}"
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.charts.id}"

    cache_policy_id        = data.aws_cloudfront_cache_policy.caching_optimized.id
    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    dynamic "function_association" {
      for_each = var.enable_cloudfront_basic_auth ? [1] : []
      content {
        event_type   = "viewer-request"
        function_arn = aws_cloudfront_function.basic_auth[0].arn
      }
    }
  }

  price_class = "PriceClass_All" # Serves from all edge locations (required for flat-rate / free plan compatibility)

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = var.custom_domain_name == "" ? true : false
    acm_certificate_arn            = var.custom_domain_name != "" ? var.acm_certificate_arn : null
    ssl_support_method             = var.custom_domain_name != "" ? "sni-only" : null
    minimum_protocol_version       = var.custom_domain_name != "" ? "TLSv1.2_2021" : null
  }

  tags = merge(local.common_tags, {
    Component = "cdn"
  })
}

# 4. S3 Bucket Policy allowing CloudFront OAC read access
resource "aws_s3_bucket_policy" "charts_oac" {
  count  = var.enable_cloudfront ? 1 : 0
  bucket = aws_s3_bucket.charts.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudFrontServicePrincipalReadOnly"
        Effect    = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.charts.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.s3_distribution[0].arn
          }
        }
      }
    ]
  })
}
