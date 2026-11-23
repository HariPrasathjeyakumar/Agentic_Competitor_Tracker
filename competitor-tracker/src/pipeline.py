"""Pipeline orchestrator enforcing strict information barriers across all agents."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src import PROJECT_ROOT, load_config, resolve_path
from src.analyst import run_analyst
from src.classifier import run_classifier
from src.diff_engine import DiffEvent, run_diff
from src.evidence import verify_quote
from src.llm import FakeLLMClient, LLMClient
from src.schemas import SingleAgentOutput, parse_json_output
from src.scout import run_scout
from src.scribe import append_event, digest_line, print_digest
from src.strategist import run_strategist

VALID_ABLATIONS = ("full", "no_classifier", "single_agent")


def compute_event_id(competitor: str, page: str, as_of: str, added_text: str) -> str:
    payload = f"{competitor}|{page}|{as_of}|{added_text[:200]}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _run_single_agent(
    llm: Any,
    inputs: dict[str, Any],
    max_retries: int = 1,
    prompts_dir: Path | None = None,
) -> tuple[bool, dict[str, Any] | None, str, str, str | None, int]:
    p_dir = prompts_dir if prompts_dir is not None else PROJECT_ROOT / "prompts"
    template = (p_dir / "single_agent.txt").read_text(encoding="utf-8")
    features = inputs.get("key_features", [])
    features_str = "\n".join(f"- {f}" for f in features) if isinstance(features, list) else str(features)

    base_prompt = (
        template.replace("{competitor_name}", str(inputs["competitor_name"]))
        .replace("{product_name}", str(inputs["product_name"]))
        .replace("{product_description}", str(inputs["product_description"]))
        .replace("{key_features}", features_str)
        .replace("{added_text}", str(inputs["added_text"]))
    )

    prompt = base_prompt
    tokens = 0
    last_error = ""
    provider = ""
    model = ""

    for attempt in range(max_retries + 1):
        res = llm.complete(prompt, agent="single_agent")
        tokens += res.approx_tokens
        provider = res.provider
        model = res.model
        try:
            parsed = parse_json_output(res.text, SingleAgentOutput)
            return True, parsed.model_dump(), provider, model, None, tokens
        except ValueError as exc:
            last_error = str(exc)
            if attempt < max_retries:
                prompt = (
                    f"{base_prompt}\n\n"
                    f"Your previous output was invalid: {last_error}. Return ONLY valid JSON."
                )

    return False, None, provider, model, last_error, tokens


def _default_dry_run_llm() -> FakeLLMClient:
    """Build a deterministic dry-run FakeLLMClient that picks verbatim quotes from the prompt."""
    def responder(prompt: str, agent: str) -> str:
        if agent == "classifier":
            is_launch = any(
                kw in prompt.lower()
                for kw in ("ai", "summarize", "integration", "self-hosted", "generally available", "introducing")
            ) and "fixed a memory leak" not in prompt.lower()
            return json.dumps({
                "is_feature_launch": is_launch,
                "category": "new_feature" if is_launch else "blog_noise",
                "feature_name": "Locus AI Thread Summarization" if is_launch else None,
                "confidence": 0.92,
            })
        if agent == "analyst":
            marker = "Added Text from Competitor Page:\n"
            snippet = prompt.split(marker, 1)[1].strip() if marker in prompt else prompt.strip()
            quote = snippet.splitlines()[0][:120] if snippet else "New feature launched for engineering teams"
            if len(quote) < 15:
                quote = (snippet[:120] if len(snippet) >= 15 else "New product capability released today")
            return json.dumps({
                "threat_level": "HIGH",
                "reasoning": (
                    "This release targets small engineering teams seeking fast thread comprehension. "
                    "It increases competitive pressure around daily collaboration workflows."
                ),
                "evidence_quote": quote,
                "overlaps_roadmap_item": "Channels and threads",
                "confidence": 0.89,
            })
        if agent == "strategist":
            return json.dumps({
                "recommendation": "differentiate",
                "actions": [
                    "Highlight TeamChat's privacy-first self-hosted architecture with zero third-party AI data retention.",
                    "Publish a technical comparison showing simple workspace setup for small engineering teams.",
                ],
                "contests_analyst": False,
                "contest_reason": None,
            })
        if agent == "single_agent":
            marker = "Added Text from Competitor Page:\n"
            snippet = prompt.split(marker, 1)[1].strip() if marker in prompt else prompt.strip()
            quote = snippet.splitlines()[0][:120] if snippet else "New feature launched for engineering teams"
            if len(quote) < 15:
                quote = "New product capability released today"
            return json.dumps({
                "classifier": {
                    "is_feature_launch": True,
                    "category": "new_feature",
                    "feature_name": "Locus AI Thread Summarization",
                    "confidence": 0.90,
                },
                "analyst": {
                    "threat_level": "HIGH",
                    "reasoning": (
                        "This release targets small engineering teams seeking fast thread comprehension. "
                        "It increases competitive pressure around daily collaboration workflows."
                    ),
                    "evidence_quote": quote,
                    "overlaps_roadmap_item": "Channels and threads",
                    "confidence": 0.87,
                },
                "strategist": {
                    "recommendation": "differentiate",
                    "actions": [
                        "Emphasize self-hosted privacy guarantees over cloud-hosted AI summaries.",
                    ],
                    "contests_analyst": False,
                    "contest_reason": None,
                },
            })
        return "{}"

    return FakeLLMClient(responses=responder, provider="dry_run", model="fake-dry-run")


def process_diff_event(
    diff_event: DiffEvent,
    config: dict[str, Any],
    llm: Any,
    ablation: str = "full",
    prompts_dir: Path | None = None,
) -> dict[str, Any]:
    """Process one DiffEvent through the configured pipeline ablation with strict information barriers."""
    if ablation not in VALID_ABLATIONS:
        raise ValueError(f"Unsupported ablation '{ablation}'. Choose from {VALID_ABLATIONS}.")

    product = config.get("product", {})
    max_retries = int(config.get("thresholds", {}).get("max_retries", 1))
    p_dir = prompts_dir if prompts_dir is not None else PROJECT_ROOT / "prompts"

    event_id = compute_event_id(
        diff_event.competitor,
        diff_event.page,
        diff_event.as_of,
        diff_event.added_text,
    )
    detected_at = datetime.now(timezone.utc).isoformat()

    classifier_out: dict[str, Any] | None = None
    analyst_out: dict[str, Any] | None = None
    strategist_out: dict[str, Any] | None = None
    models: dict[str, str] = {}
    tokens_approx = 0
    status = "confirmed"
    status_reason = "All pipeline checks passed."

    if ablation == "single_agent":
        ok, payload, provider, model, err, tok = _run_single_agent(
            llm=llm,
            inputs={
                "competitor_name": diff_event.competitor,
                "product_name": product["name"],
                "product_description": product["description"],
                "key_features": product["key_features"],
                "added_text": diff_event.added_text,
            },
            max_retries=max_retries,
            prompts_dir=p_dir,
        )
        tokens_approx += tok
        models["single_agent"] = f"{provider}:{model}"
        if not ok or payload is None:
            status = "parse_failed"
            status_reason = f"single_agent failed validation: {err}"
        else:
            classifier_out = payload["classifier"]
            if not classifier_out["is_feature_launch"]:
                status = "dismissed"
                status_reason = f"Classified as {classifier_out['category']} (not a feature launch)."
            else:
                analyst_out = payload["analyst"]
                if not verify_quote(analyst_out["evidence_quote"], diff_event.new_text):
                    status = "invalid_evidence"
                    status_reason = "Analyst evidence_quote was not found verbatim in full snapshot."
                else:
                    strategist_out = payload["strategist"]
                    status = "confirmed"
                    status_reason = "Single-agent output validated and evidence verified."
    else:
        # Step 1: Classifier (only in "full" ablation; skipped in "no_classifier")
        if ablation == "full":
            c_inputs = {
                "competitor_name": diff_event.competitor,
                "added_text": diff_event.added_text,
            }
            c_res = run_classifier(llm, c_inputs, max_retries=max_retries, prompts_dir=p_dir)
            tokens_approx += c_res.tokens_approx
            models["classifier"] = f"{c_res.provider}:{c_res.model}"
            if not c_res.ok or c_res.output is None:
                status = "parse_failed"
                status_reason = f"Classifier parse failed: {c_res.error}"
                return _build_event_record(
                    event_id, diff_event, detected_at, classifier_out, analyst_out,
                    strategist_out, status, models, ablation, status_reason, tokens_approx,
                )

            classifier_out = c_res.output
            if not classifier_out["is_feature_launch"]:
                status = "dismissed"
                status_reason = f"Classified as {classifier_out['category']} (not a feature launch)."
                return _build_event_record(
                    event_id, diff_event, detected_at, classifier_out, analyst_out,
                    strategist_out, status, models, ablation, status_reason, tokens_approx,
                )

        # Step 2: Analyst (sees classifier output, competitor name, product desc, key features, added_text)
        a_inputs = {
            "competitor_name": diff_event.competitor,
            "product_name": product["name"],
            "product_description": product["description"],
            "key_features": product["key_features"],
            "classification_json": classifier_out if classifier_out is not None else {"skipped": True},
            "added_text": diff_event.added_text,
        }
        a_res = run_analyst(llm, a_inputs, max_retries=max_retries, prompts_dir=p_dir)
        tokens_approx += a_res.tokens_approx
        models["analyst"] = f"{a_res.provider}:{a_res.model}"
        if not a_res.ok or a_res.output is None:
            status = "parse_failed"
            status_reason = f"Analyst parse failed: {a_res.error}"
            return _build_event_record(
                event_id, diff_event, detected_at, classifier_out, analyst_out,
                strategist_out, status, models, ablation, status_reason, tokens_approx,
            )
        analyst_out = a_res.output

        # Step 3: Deterministic Evidence Check (sees ONLY evidence_quote and full snapshot text)
        if not verify_quote(analyst_out["evidence_quote"], diff_event.new_text):
            status = "invalid_evidence"
            status_reason = "Analyst evidence_quote was not found verbatim in full snapshot."
            return _build_event_record(
                event_id, diff_event, detected_at, classifier_out, analyst_out,
                strategist_out, status, models, ablation, status_reason, tokens_approx,
            )

        # Step 4: Strategist (sees ONLY Analyst JSON output and product description; NEVER raw snapshot or added_text)
        s_inputs = {
            "product_name": product["name"],
            "product_description": product["description"],
            "analyst_json": analyst_out,
        }
        s_res = run_strategist(llm, s_inputs, max_retries=max_retries, prompts_dir=p_dir)
        tokens_approx += s_res.tokens_approx
        models["strategist"] = f"{s_res.provider}:{s_res.model}"
        if not s_res.ok or s_res.output is None:
            status = "parse_failed"
            status_reason = f"Strategist parse failed: {s_res.error}"
            return _build_event_record(
                event_id, diff_event, detected_at, classifier_out, analyst_out,
                strategist_out, status, models, ablation, status_reason, tokens_approx,
            )
        strategist_out = s_res.output
        status = "confirmed"
        status_reason = "Feature launch verified and strategic action recorded."

    return _build_event_record(
        event_id, diff_event, detected_at, classifier_out, analyst_out,
        strategist_out, status, models, ablation, status_reason, tokens_approx,
    )


def _build_event_record(
    event_id: str,
    diff_event: DiffEvent,
    detected_at: str,
    classifier_out: dict[str, Any] | None,
    analyst_out: dict[str, Any] | None,
    strategist_out: dict[str, Any] | None,
    status: str,
    models: dict[str, str],
    ablation: str,
    status_reason: str,
    tokens_approx: int,
) -> dict[str, Any]:
    contested = bool(strategist_out.get("contests_analyst")) if isinstance(strategist_out, dict) else False
    return {
        "event_id": event_id,
        "competitor": diff_event.competitor,
        "page": diff_event.page,
        "as_of": diff_event.as_of,
        "detected_at": detected_at,
        "classifier": classifier_out,
        "analyst": analyst_out,
        "strategist": strategist_out,
        "status": status,
        "contested": contested,
        "models": models,
        "ablation": ablation,
        "status_reason": status_reason,
        "tokens_approx": tokens_approx,
    }


def run_monitor_cycle(
    config: dict[str, Any],
    as_of: date,
    llm: Any = None,
    dry_run: bool = False,
    ablation: str = "full",
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute Scout -> Diff-Engine -> Agents -> Scribe for one monitoring cycle."""
    root = base_dir if base_dir is not None else PROJECT_ROOT
    saved_paths = run_scout(config, as_of=as_of, base_dir=root)
    diff_events, diff_stats = run_diff(config, as_of=as_of, current_paths=saved_paths, base_dir=root)

    active_llm = llm
    if active_llm is None:
        active_llm = _default_dry_run_llm() if dry_run else LLMClient(config=config, base_dir=root)

    real_feed_path = resolve_path(config, "feed_path", base_dir=root)
    feed_path = (real_feed_path.parent / "feed_dryrun.json") if dry_run else real_feed_path

    status_counts = {
        "confirmed": 0,
        "dismissed": 0,
        "invalid_evidence": 0,
        "parse_failed": 0,
    }
    recorded_events: list[dict[str, Any]] = []
    digests: list[str] = []
    total_tokens = 0
    calls_before = getattr(active_llm, "calls_made", 0)

    prompts_dir = root / "prompts"
    for diff_ev in diff_events:
        record = process_diff_event(
            diff_ev,
            config=config,
            llm=active_llm,
            ablation=ablation,
            prompts_dir=prompts_dir,
        )
        append_event(feed_path, record)
        print_digest(record)
        digests.append(digest_line(record))
        recorded_events.append(record)
        total_tokens += int(record.get("tokens_approx", 0))
        st = record["status"]
        if st in status_counts:
            status_counts[st] += 1

    calls_after = getattr(active_llm, "calls_made", 0)
    summary = {
        "as_of": as_of.isoformat(),
        "ablation": ablation,
        "dry_run": dry_run,
        "pages_checked": diff_stats["pages_checked"],
        "baseline_pages": diff_stats["baseline"],
        "below_threshold": diff_stats["below_threshold"],
        "changed_events": diff_stats["changed"],
        "counts": status_counts,
        "llm_calls": max(0, calls_after - calls_before),
        "approx_tokens": total_tokens,
        "events": recorded_events,
        "digests": digests,
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }

    summary_path = real_feed_path.parent / ("last_run_dryrun.json" if dry_run else "last_run_summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Competitor Tracker monitoring pipeline.")
    parser.add_argument("--as-of", required=True, help="Target date in YYYY-MM-DD format.")
    parser.add_argument(
        "--ablation",
        default="full",
        choices=list(VALID_ABLATIONS),
        help="Pipeline ablation mode.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use deterministic FakeLLMClient and write to data/feed_dryrun.json.",
    )
    args = parser.parse_args(argv)

    try:
        as_of_date = date.fromisoformat(args.as_of)
    except ValueError:
        print(f"Invalid --as-of date '{args.as_of}'. Expected YYYY-MM-DD.", file=sys.stderr)
        return 2

    config = load_config()
    summary = run_monitor_cycle(
        config=config,
        as_of=as_of_date,
        dry_run=args.dry_run,
        ablation=args.ablation,
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "events"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
