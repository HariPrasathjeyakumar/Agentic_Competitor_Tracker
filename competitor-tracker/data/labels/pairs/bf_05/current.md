# Locus Product Changelog

Last updated: November 10, 2026

## November 8, 2026 — Keyboard Shortcut Palette
Quickly jump between channels, unread threads, and direct messages using Cmd+K across desktop and web clients.

## October 29, 2026 — Markdown Code Blocks
Paste multi-line snippets with syntax highlighting for Python, TypeScript, Go, and Rust inside any channel thread.

## October 15, 2026 — Custom Notification Schedules
Configure quiet hours per workspace timezone so engineers are never paged during off-hours unless tagged in an incident channel.

Copyright 2026 Locus Labs Inc. All rights reserved.
Privacy Policy | Terms of Service | Cookie Settings

## Reliability Patch — Webhook Retry Queue Correction
Fixed a bug where failed outbound webhooks returned HTTP 429 retries without honoring the Retry-After header. Resolved an edge case where deleted draft messages reappeared after browser refresh.
