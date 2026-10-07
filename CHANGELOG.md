# Changelog

All notable changes to this project will be documented in this file.

## 2026-10-07

### Added

- **Per-Device Timezone Configuration**: Support for explicit IANA timezones per device across Terraform infrastructure, DynamoDB metadata, and EventBridge triggers.
- **Timezone-Aware Dashboard**: Dynamic calculation of "Today" and "Yesterday" day tags based on each device's configured timezone.
- **Timezone in Metadata & Sidecars**: Export device timezones into `metadata.json` registry and chart JSON sidecars.

### Fixed

- **Cross-Timezone Dashboard Labeling ([#1](https://github.com/nobudev7/PiLambdaChart/issues/1))**: Prevented "Today" charts from appearing as "Yesterday" (or vice versa) when accessed from a different browser timezone.
- **Status & Calendar Date Shifts**: Aligned device status timestamps and day boundaries with the device's local calendar day rather than the browser's local timezone.
