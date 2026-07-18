# ─────────────────────────────────────────────────────────────────────────────
# Shared Tag Strategy
# ─────────────────────────────────────────────────────────────────────────────
# All AWS resources in this project must include these common tags.
#
# Usage in any resource block:
#
#   tags = merge(local.common_tags, {
#     Component = "my-component-name"
#   })
#
# The `merge()` call lets each resource override or extend the common tags
# with its own Component label while still inheriting all shared tags.
# ─────────────────────────────────────────────────────────────────────────────

locals {
  common_tags = {
    # Identifies the broader product or business domain.
    Project = var.project_name

    # Marks that all resources are managed by Terraform (not clicked together
    # in the console), which prevents config drift and aids audits.
    ManagedBy = "terraform"

  }
}
