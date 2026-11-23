"""Synthetic labeled dataset generator with stratified dev/heldout split and snapshot pairs."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from src import PROJECT_ROOT, load_config, resolve_path

_BASE_CHANGELOG = """# Locus Product Changelog

Last updated: November 10, 2026

## November 8, 2026 — Keyboard Shortcut Palette
Quickly jump between channels, unread threads, and direct messages using Cmd+K across desktop and web clients.

## October 29, 2026 — Markdown Code Blocks
Paste multi-line snippets with syntax highlighting for Python, TypeScript, Go, and Rust inside any channel thread.

## October 15, 2026 — Custom Notification Schedules
Configure quiet hours per workspace timezone so engineers are never paged during off-hours unless tagged in an incident channel.

Copyright 2026 Locus Labs Inc. All rights reserved.
Privacy Policy | Terms of Service | Cookie Settings
"""

_BASE_PRICING = """# Locus Pricing Plans

Last updated: November 10, 2026

## Free — For small teams getting started ($0/user/month)
- Up to 10 active members
- 90 days of searchable message history
- Standard channel and thread messaging
- 25 MB file upload limit

## Team — For growing engineering organizations ($8/user/month)
- Unlimited active members and message history
- Up to 250 MB file sharing
- Standard webhook and CI notifications
- Role-based channel permissions

## Enterprise — For regulated organizations ($18/user/month)
- SAML SSO and SCIM provisioning
- 99.99% uptime SLA and audit log exports
- Dedicated regional cloud hosting

Copyright 2026 Locus Labs Inc. All rights reserved.
Privacy Policy | Terms of Service | Cookie Settings
"""


def _build_cases() -> list[dict[str, Any]]:
    """Return 40 realistic labeled competitor page changes (16 launches, 24 non-launches)."""
    cases: list[dict[str, Any]] = [
        # --- 16 REAL FEATURES (varied threat levels: HIGH, MEDIUM, LOW) ---
        {
            "id": "rf_01",
            "page": "changelog",
            "kind": "real_feature",
            "label_is_launch": True,
            "label_threat": "HIGH",
            "feature_name": "One-Click Thread Summarization",
            "added_text": (
                "## November 20, 2026 — One-Click Thread Summarization\n"
                "Locus now ships built-in one-click thread summaries across every channel and direct message thread. "
                "Engineers can condense 200-message incident threads into decisions, owners, and open blockers in under two seconds."
            ),
        },
        {
            "id": "rf_02",
            "page": "changelog",
            "kind": "real_feature",
            "label_is_launch": True,
            "label_threat": "HIGH",
            "feature_name": "Two-Way GitHub & Jira Sync",
            "added_text": (
                "## November 19, 2026 — Two-Way GitHub & Jira Sync\n"
                "Connect repositories and Jira boards directly to Locus channels starting today. "
                "Engineers can approve pull requests, transition Jira ticket statuses, and comment on issues without leaving their chat threads."
            ),
        },
        {
            "id": "rf_03",
            "page": "changelog",
            "kind": "real_feature",
            "label_is_launch": True,
            "label_threat": "HIGH",
            "feature_name": "Self-Hosted Docker & Kubernetes Edition",
            "added_text": (
                "## November 18, 2026 — Self-Hosted Docker & Kubernetes Edition\n"
                "Locus Self-Hosted is now generally available as a single-command Docker Compose bundle and Helm chart. "
                "Privacy-focused engineering teams can deploy Locus inside air-gapped VPCs with zero external telemetry."
            ),
        },
        {
            "id": "rf_04",
            "page": "pricing",
            "kind": "real_feature",
            "label_is_launch": True,
            "label_threat": "HIGH",
            "feature_name": "Unlimited Message History on Free Tier",
            "added_text": (
                "## Free Tier Feature Expansion — Unlimited Message History\n"
                "- Unlimited searchable message history is now live for every Free workspace, removing the previous 90-day retention cap.\n"
                "- Teams also receive 150 MB file attachments on the Free plan at no extra cost."
            ),
        },
        {
            "id": "rf_05",
            "page": "changelog",
            "kind": "real_feature",
            "label_is_launch": True,
            "label_threat": "HIGH",
            "feature_name": "500 MB Engineering Artifact Sharing",
            "added_text": (
                "## November 17, 2026 — 500 MB Engineering Artifact Sharing\n"
                "All paid and trial Locus workspaces can now upload build logs, crash dumps, and screen recordings up to 500 MB per file. "
                "Uploaded archives include inline previewers for JSON traces and zip manifests."
            ),
        },
        {
            "id": "rf_06",
            "page": "changelog",
            "kind": "real_feature",
            "label_is_launch": True,
            "label_threat": "MEDIUM",
            "feature_name": "Live Voice Huddles with Screen Share",
            "added_text": (
                "## November 16, 2026 — Live Voice Huddles with Screen Share\n"
                "Start lightweight audio huddles directly inside any Locus channel with low-latency cursor-annotated screen sharing. "
                "Huddles support up to 15 concurrent engineers without spinning up an external video meeting link."
            ),
        },
        {
            "id": "rf_07",
            "page": "changelog",
            "kind": "real_feature",
            "label_is_launch": True,
            "label_threat": "MEDIUM",
            "feature_name": "Automated On-Call Pager Escalation",
            "added_text": (
                "## November 15, 2026 — Automated On-Call Pager Escalation\n"
                "Locus Incident Channels now ship automated escalation policies that page secondary engineers if an alert goes unacknowledged for five minutes. "
                "Acknowledge or silence pages via slash commands right inside the thread."
            ),
        },
        {
            "id": "rf_08",
            "page": "changelog",
            "kind": "real_feature",
            "label_is_launch": True,
            "label_threat": "MEDIUM",
            "feature_name": "Cross-Workspace Shared Channels",
            "added_text": (
                "## November 14, 2026 — Cross-Workspace Shared Channels\n"
                "Collaborate with external contractors and partner engineering teams using federated shared channels. "
                "Admins retain full message retention policies and can revoke external domain access in one click."
            ),
        },
        {
            "id": "rf_09",
            "page": "changelog",
            "kind": "real_feature",
            "label_is_launch": True,
            "label_threat": "MEDIUM",
            "feature_name": "Semantic Channel Search",
            "added_text": (
                "## November 13, 2026 — Semantic Channel Search\n"
                "Locus Search now supports natural-language queries across historical channels, attachments, and code blocks. "
                "Ask questions like 'how did we rotate the staging Redis keys' and jump straight to the resolved thread."
            ),
        },
        {
            "id": "rf_10",
            "page": "pricing",
            "kind": "real_feature",
            "label_is_launch": True,
            "label_threat": "MEDIUM",
            "feature_name": "Zero-Config Slack Migration Importer",
            "added_text": (
                "## Team Plan Addition — Zero-Config Slack Migration Importer\n"
                "- Added a guided self-serve migration importer that transfers channels, threaded replies, emoji reactions, and user mappings in under ten minutes.\n"
                "- Preserves original timestamps and private channel membership rules automatically."
            ),
        },
        {
            "id": "rf_11",
            "page": "changelog",
            "kind": "real_feature",
            "label_is_launch": True,
            "label_threat": "MEDIUM",
            "feature_name": "Workflow Automations Builder",
            "added_text": (
                "## November 12, 2026 — Workflow Automations Builder\n"
                "Build no-code channel triggers that route bug reports, collect standup updates, and post daily release checklists automatically. "
                "Templates for engineering triage and onboarding are available immediately in workspace settings."
            ),
        },
        {
            "id": "rf_12",
            "page": "changelog",
            "kind": "real_feature",
            "label_is_launch": True,
            "label_threat": "LOW",
            "feature_name": "Enterprise FINRA & SEC Compliance Exports",
            "added_text": (
                "## November 11, 2026 — Enterprise FINRA & SEC Compliance Exports\n"
                "Enterprise financial institutions can now enable WORM-compliant archival exports to Smarsh and Global Relay. "
                "Requires an Enterprise contract with dedicated compliance administrator provisioning."
            ),
        },
        {
            "id": "rf_13",
            "page": "changelog",
            "kind": "real_feature",
            "label_is_launch": True,
            "label_threat": "LOW",
            "feature_name": "Custom SAML Attribute Role Mapping",
            "added_text": (
                "## November 9, 2026 — Custom SAML Attribute Role Mapping\n"
                "Identity administrators on Enterprise plans can now map Okta and Azure AD group attributes directly to Locus channel security groups. "
                "Role updates propagate during the next SAML assertion refresh."
            ),
        },
        {
            "id": "rf_14",
            "page": "changelog",
            "kind": "real_feature",
            "label_is_launch": True,
            "label_threat": "LOW",
            "feature_name": "Desktop Status Sync with Apple Focus",
            "added_text": (
                "## November 7, 2026 — Desktop Status Sync with Apple Focus\n"
                "Our macOS desktop client now syncs your availability status automatically with macOS Focus modes. "
                "When Deep Work Focus is active on your Mac, Locus sets your presence to Do Not Disturb."
            ),
        },
        {
            "id": "rf_15",
            "page": "pricing",
            "kind": "real_feature",
            "label_is_launch": True,
            "label_threat": "LOW",
            "feature_name": "Multi-Region EU/APAC Data Pinning",
            "added_text": (
                "## Enterprise Plan Addition — Multi-Region EU/APAC Data Pinning\n"
                "- Enterprise customers can now select Frankfurt, Tokyo, or Sydney storage regions for workspace backups and search indexes.\n"
                "- Available at provisioning for organizations exceeding 500 licensed seats."
            ),
        },
        {
            "id": "rf_16",
            "page": "changelog",
            "kind": "real_feature",
            "label_is_launch": True,
            "label_threat": "LOW",
            "feature_name": "Custom Animated Workspace Emoji Packs",
            "added_text": (
                "## November 6, 2026 — Custom Animated Workspace Emoji Packs\n"
                "Workspace members can now upload WebP animated emoji packs and organize team reactions into shared folders. "
                "Includes bulk ZIP import and reaction usage analytics for community managers."
            ),
        },
        # --- 24 NEGATIVE CASES (6 bug_fix, 6 cosmetic, 6 blog_noise, 6 pricing_change) ---
        {
            "id": "bf_01",
            "page": "changelog",
            "kind": "bug_fix",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Maintenance Patch v4.12.3 — Notification Badge Fix\n"
                "Resolved a race condition in the Electron desktop wrapper where unread mention counters failed to clear after switching workspaces rapidly. "
                "Also patched a crash affecting Wayland Linux users during screen sharing cleanup."
            ),
        },
        {
            "id": "bf_02",
            "page": "changelog",
            "kind": "bug_fix",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Stability Update v4.12.2 — WebSocket Reconnect Hardening\n"
                "Fixed an issue where mobile clients remained stuck in 'Connecting...' after transitioning from corporate Wi-Fi to cellular LTE. "
                "Reduced duplicate push notification deliveries on iOS 19 devices."
            ),
        },
        {
            "id": "bf_03",
            "page": "changelog",
            "kind": "bug_fix",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Patch Release v4.12.1 — Search Index Sync Fix\n"
                "Addressed an indexing delay that caused edited thread messages to appear with stale text in global search results for up to ten minutes. "
                "Corrected timezone offset rendering in CSV message export logs."
            ),
        },
        {
            "id": "bf_04",
            "page": "changelog",
            "kind": "bug_fix",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Hotfix v4.12.0 — Memory Leak in Media Previews\n"
                "Eliminated a memory leak triggered when scrolling rapidly through channels containing large inline PNG screenshots. "
                "Fixed keyboard focus trapping inside the emoji reaction picker on Firefox."
            ),
        },
        {
            "id": "bf_05",
            "page": "changelog",
            "kind": "bug_fix",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Reliability Patch — Webhook Retry Queue Correction\n"
                "Fixed a bug where failed outbound webhooks returned HTTP 429 retries without honoring the Retry-After header. "
                "Resolved an edge case where deleted draft messages reappeared after browser refresh."
            ),
        },
        {
            "id": "bf_06",
            "page": "changelog",
            "kind": "bug_fix",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Desktop Bug Fix — Tray Icon & Auto-Updater\n"
                "Fixed a Windows 11 system tray icon blur issue on 150% DPI scaling displays and resolved an updater permission prompt error for standard non-admin accounts. "
                "No user workflow changes are included in this patch."
            ),
        },
        {
            "id": "cos_01",
            "page": "changelog",
            "kind": "cosmetic",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Visual Refresh — Sidebar Typography & Spacing\n"
                "Updated channel list font weights, tightened vertical row padding by 2 pixels, and introduced softer slate divider hairlines across the workspace sidebar for calmer visual contrast during long sessions."
            ),
        },
        {
            "id": "cos_02",
            "page": "changelog",
            "kind": "cosmetic",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Brand Polish — Updated App Icon & Loading Skeleton\n"
                "Refreshed the desktop dock icon with updated geometric proportions and replaced the legacy spinner animation with a neutral shimmer skeleton while threads hydrate on slow networks."
            ),
        },
        {
            "id": "cos_03",
            "page": "pricing",
            "kind": "cosmetic",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Pricing Page Copy & Card Alignment Update\n"
                "Reordered bullet points across the Free, Team, and Enterprise columns for clearer side-by-side reading and updated button labels from 'Start Trial' to 'Create Workspace' with identical underlying plan entitlements."
            ),
        },
        {
            "id": "cos_04",
            "page": "changelog",
            "kind": "cosmetic",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## UI Polish — Refined Thread Drawer Borders\n"
                "Adjusted border radius tokens on modal dialogs and refined timestamp contrast ratios in light theme so secondary metadata passes WCAG AA legibility guidelines across calibrated monitors."
            ),
        },
        {
            "id": "cos_05",
            "page": "changelog",
            "kind": "cosmetic",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Header Navigation Rearrangement\n"
                "Moved the Help Center link from the top navigation bar into the workspace profile dropdown menu and standardized button corner radii across settings tabs without altering functionality."
            ),
        },
        {
            "id": "cos_06",
            "page": "pricing",
            "kind": "cosmetic",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Updated Customer Logos & Typography on Pricing\n"
                "Replaced legacy partner logo SVGs in the social proof strip below the pricing grid and bumped section headings by 2px for improved visual hierarchy on ultrawide desktop displays."
            ),
        },
        {
            "id": "bn_01",
            "page": "changelog",
            "kind": "blog_noise",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Engineering Essay: Why Async Thread Summaries Matter in 2027\n"
                "In this week's engineering blog post, our product research team explores how distributed startups suffer from thread overload and debates theoretical design patterns for AI summarization tools—no product changes are shipping yet."
            ),
        },
        {
            "id": "bn_02",
            "page": "changelog",
            "kind": "blog_noise",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Customer Spotlight: How Northstar Robotics Runs Daily Standups\n"
                "Read our new case study profiling how a 45-person robotics team uses existing Locus channels and manual checklists to coordinate firmware releases across Munich and Austin."
            ),
        },
        {
            "id": "bn_03",
            "page": "changelog",
            "kind": "blog_noise",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## We Are Hiring Principal Distributed Systems Engineers\n"
                "Locus is expanding our core messaging infrastructure group across North America and Europe. "
                "If you love Rust, Raft consensus, and low-latency WebSockets, visit our careers page to meet the team and apply."
            ),
        },
        {
            "id": "bn_04",
            "page": "changelog",
            "kind": "blog_noise",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Thinking About Self-Hosted Security: Lessons From Our Advisory Board\n"
                "Our CISO shares reflections from a recent roundtable on why regulated engineering organizations care about VPC isolation, air-gapped deployments, and auditability—without announcing any new deployment product."
            ),
        },
        {
            "id": "bn_05",
            "page": "changelog",
            "kind": "blog_noise",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Community Meetup Recap: Building Developer Tools in Berlin\n"
                "Thank you to the 180 engineers who joined our autumn systems engineering meetup last Thursday. "
                "Slides and lightning talk recordings covering Go profiling and local-first databases are now posted on our community hub."
            ),
        },
        {
            "id": "bn_06",
            "page": "changelog",
            "kind": "blog_noise",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Annual Transparency & Reliability Report 2026\n"
                "We published our yearly operational review detailing 99.98% message delivery uptime, zero security incidents, and our roadmap philosophy for keeping team chat calm and predictable next year."
            ),
        },
        {
            "id": "pc_01",
            "page": "pricing",
            "kind": "pricing_change",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Team Plan Billing Adjustment — Annual vs. Monthly Rates\n"
                "Effective January 1, 2027, the Team plan monthly rate changes from $8 to $10 per active user per month, while annual prepayment remains locked at $8 per user per month with no changes to included features."
            ),
        },
        {
            "id": "pc_02",
            "page": "pricing",
            "kind": "pricing_change",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Enterprise Minimum Seat Requirement Update\n"
                "Updated Enterprise contract terms to require a 25-seat minimum commitment on new annual agreements and introduced quarterly invoicing options in EUR and GBP alongside USD."
            ),
        },
        {
            "id": "pc_03",
            "page": "pricing",
            "kind": "pricing_change",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Academic & Non-Profit Discount Policy Clarification\n"
                "Verified non-profit organizations and university research labs now receive a flat 40% discount on Team and Enterprise subscriptions; all included product capabilities remain unchanged."
            ),
        },
        {
            "id": "pc_04",
            "page": "pricing",
            "kind": "pricing_change",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Fair-Billing Proration Policy Update\n"
                "We updated our billing FAQ to clarify automated seat credits when team members become inactive for 14 consecutive days, ensuring organizations only pay for active monthly contributors."
            ),
        },
        {
            "id": "pc_05",
            "page": "pricing",
            "kind": "pricing_change",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Startup Program Credits Extension\n"
                "Eligible seed-stage startups affiliated with partner incubators can now apply a $1,000 billing credit toward their first year on the Team tier without altering plan limits or product features."
            ),
        },
        {
            "id": "pc_06",
            "page": "pricing",
            "kind": "pricing_change",
            "label_is_launch": False,
            "label_threat": None,
            "feature_name": None,
            "added_text": (
                "## Multi-Year Enterprise Price Lock Guarantee\n"
                "Organizations signing 24-month or 36-month Enterprise agreements before quarter-end receive a contractual renewal price cap of 3% annually with identical feature entitlements."
            ),
        },
    ]
    return cases


def generate_dataset(config: dict[str, Any] | None = None, base_dir: Path | None = None) -> dict[str, Any]:
    """Generate labeled cases, stratified dev/heldout splits, and snapshot pairs."""
    root = base_dir if base_dir is not None else PROJECT_ROOT
    cfg = config if config is not None else load_config(root / "config.yaml")

    labels_dir = resolve_path(cfg, "labels_dir", base_dir=root)
    pairs_dir = labels_dir / "pairs"
    labels_dir.mkdir(parents=True, exist_ok=True)
    pairs_dir.mkdir(parents=True, exist_ok=True)

    eval_cfg = cfg.get("evaluation", {})
    dev_fraction = float(eval_cfg.get("dev_fraction", 0.6))
    split_seed = int(eval_cfg.get("split_seed", 42))

    cases = _build_cases()
    for c in cases:
        if len(c["added_text"]) < 200:
            raise ValueError(f"Case {c['id']} added_text shorter than 200 chars ({len(c['added_text'])})")

    # Stratified split by kind
    rng = random.Random(split_seed)
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        by_kind.setdefault(case["kind"], []).append(case)

    dev_cases: list[dict[str, Any]] = []
    heldout_cases: list[dict[str, Any]] = []
    for kind in sorted(by_kind.keys()):
        group = list(by_kind[kind])
        rng.shuffle(group)
        n_dev = max(1, round(len(group) * dev_fraction))
        for idx, item in enumerate(group):
            copy_item = dict(item)
            if idx < n_dev:
                copy_item["split"] = "dev"
                dev_cases.append(copy_item)
            else:
                copy_item["split"] = "heldout"
                heldout_cases.append(copy_item)

    all_labeled = dev_cases + heldout_cases
    # Preserve deterministic order by id
    all_labeled.sort(key=lambda x: x["id"])
    dev_cases.sort(key=lambda x: x["id"])
    heldout_cases.sort(key=lambda x: x["id"])

    (labels_dir / "labels.json").write_text(json.dumps(all_labeled, indent=2), encoding="utf-8")
    (labels_dir / "dev.json").write_text(json.dumps(dev_cases, indent=2), encoding="utf-8")
    (labels_dir / "heldout.json").write_text(json.dumps(heldout_cases, indent=2), encoding="utf-8")

    for item in all_labeled:
        base_text = _BASE_CHANGELOG if item["page"] == "changelog" else _BASE_PRICING
        current_text = f"{base_text}\n{item['added_text']}\n"
        case_dir = pairs_dir / item["id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "previous.md").write_text(base_text, encoding="utf-8")
        (case_dir / "current.md").write_text(current_text, encoding="utf-8")

    return {
        "total": len(all_labeled),
        "dev": len(dev_cases),
        "heldout": len(heldout_cases),
        "labels_dir": str(labels_dir),
    }


def main() -> int:
    summary = generate_dataset()
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
