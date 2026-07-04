# Deferred

Real-but-unscheduled items, each with a revisit trigger.

- **Vendor media-type case-sensitivity** — `parse_accept_version` compares a
  lowercased header media-type against a non-lowercased `vendor_media_type`,
  so a mixed-case vendor never matches (silently falls through to `Ignore`).
  Revisit trigger: a user configures a vendor type with uppercase letters, or
  we decide to guarantee case-insensitive media-type matching. Fix is a
  failing `tests/test_accept.py` case plus a `.lower()` on the vendor.
