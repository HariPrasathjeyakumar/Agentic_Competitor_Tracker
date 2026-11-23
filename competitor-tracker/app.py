"""Streamlit intelligence console supporting Replay (cloud-safe) and local Live modes."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

from src import PROJECT_ROOT, load_config, resolve_path
from src.pipeline import VALID_ABLATIONS, run_monitor_cycle

load_dotenv(PROJECT_ROOT / ".env", override=False)

st.set_page_config(page_title="Competitor Tracker", layout="wide")


def _has_api_keys() -> bool:
    placeholders = {"", "your_gemini_key_here", "your_groq_key_here", "MY_GEMINI_API_KEY"}
    g = os.environ.get("GEMINI_API_KEY", "").strip()
    q = os.environ.get("GROQ_API_KEY", "").strip()
    return (g not in placeholders) or (q not in placeholders)


def _mock_site_reachable(config: dict[str, Any]) -> bool:
    competitors = config.get("competitors", [])
    if not competitors:
        return False
    url = competitors[0].get("changelog_url", "")
    if not url:
        return False
    try:
        resp = requests.get(url, timeout=1.5)
        return resp.status_code < 500
    except requests.RequestException:
        return False


@st.cache_data(ttl=10)
def load_json_cached(path_str: str) -> Any | None:
    p = Path(path_str)
    if not p.exists():
        return None
    raw = p.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    return json.loads(raw)


def main() -> None:
    config = load_config()
    feed_path = resolve_path(config, "feed_path")
    eval_path = resolve_path(config, "eval_report_json")
    summary_path = feed_path.parent / "last_run_summary.json"

    keys_ready = _has_api_keys()
    mock_up = _mock_site_reachable(config)
    local_flag = os.environ.get("LOCAL_MODE", "0") == "1"
    default_index = 0 if (keys_ready and mock_up and local_flag) else 1

    st.sidebar.title("Competitor Tracker")
    mode = st.sidebar.radio("Operating Mode", ["Live", "Replay"], index=default_index)
    if mode == "Live" and not keys_ready:
        st.sidebar.warning("No API keys found in environment. Switch to Replay or run with dry-run.")

    st.title("Competitor Tracker Intelligence Console")

    tab_names = ["Monitor", "Feed", "Evaluation"]
    if mode == "Live":
        tab_names.append("Mock site control")
    tabs = st.tabs(tab_names)

    # 1. Monitor Tab
    with tabs[0]:
        st.subheader("Pipeline Monitor")
        if mode == "Replay":
            st.info("Replay mode active: reading saved artifacts only (no Scout or LLM calls).")
            saved_summary = load_json_cached(str(summary_path))
            if saved_summary:
                cols = st.columns(4)
                cols[0].metric("Pages Checked", saved_summary.get("pages_checked", 0))
                cols[1].metric("Changed Events", saved_summary.get("changed_events", 0))
                cols[2].metric("LLM Calls", saved_summary.get("llm_calls", 0))
                cols[3].metric("Approx Tokens", saved_summary.get("approx_tokens", 0))
                st.json({k: v for k, v in saved_summary.items() if k != "events"})
            else:
                st.caption("No saved run summary found yet.")
        else:
            col1, col2, col3 = st.columns(3)
            as_of = col1.date_input("As-of date", value=date(2026, 11, 23))
            ablation = col2.selectbox("Ablation", list(VALID_ABLATIONS), index=0)
            dry_run = col3.checkbox("Dry run (FakeLLMClient)", value=not keys_ready)
            if st.button("Run monitor cycle", type="primary"):
                with st.spinner("Running monitoring pipeline..."):
                    try:
                        summary = run_monitor_cycle(
                            config=config,
                            as_of=as_of,
                            dry_run=dry_run,
                            ablation=ablation,
                        )
                        load_json_cached.clear()
                        st.success("Monitor cycle completed.")
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Pages Checked", summary["pages_checked"])
                        c2.metric("Changed", summary["changed_events"])
                        c3.metric("Confirmed", summary["counts"]["confirmed"])
                        c4.metric("Approx Tokens", summary["approx_tokens"])
                        for line in summary.get("digests", []):
                            st.write(line)
                    except Exception as exc:
                        st.error(f"Monitor cycle failed: {exc}")

    # 2. Feed Tab
    with tabs[1]:
        st.subheader("Structured Intelligence Feed")
        feed_data = load_json_cached(str(feed_path))
        if not feed_data:
            st.info(f"No feed entries found at {feed_path}. Run the pipeline or generate replay fixtures.")
        else:
            statuses = sorted({ev.get("status", "unknown") for ev in feed_data})
            competitors = sorted({ev.get("competitor", "unknown") for ev in feed_data})
            f1, f2 = st.columns(2)
            sel_status = f1.multiselect("Filter by status", statuses, default=statuses)
            sel_comp = f2.multiselect("Filter by competitor", competitors, default=competitors)

            filtered = [
                ev for ev in reversed(feed_data)
                if ev.get("status") in sel_status and ev.get("competitor") in sel_comp
            ]
            st.caption(f"Showing {len(filtered)} of {len(feed_data)} event(s).")
            for ev in filtered:
                cls = ev.get("classifier") or {}
                ana = ev.get("analyst") or {}
                strat = ev.get("strategist") or {}
                title = cls.get("feature_name") or ev.get("page", "change")
                header = f"[{ev.get('status', '').upper()}] {ev.get('competitor')} — {title} ({ev.get('as_of')})"
                with st.expander(header):
                    st.write(
                        f"**Status:** `{ev.get('status')}` | **Threat:** `{ana.get('threat_level', 'N/A')}` | "
                        f"**Contested:** `{ev.get('contested')}` | **Tokens:** `{ev.get('tokens_approx', 0)}`"
                    )
                    st.write(f"**Models:** `{ev.get('models')}`")
                    if ana.get("evidence_quote"):
                        st.info(f"Evidence quote: \"{ana['evidence_quote']}\"")
                    c_a, c_b, c_c = st.columns(3)
                    c_a.markdown("**Classifier**")
                    c_a.json(cls)
                    c_b.markdown("**Analyst**")
                    c_b.json(ana)
                    c_c.markdown("**Strategist**")
                    c_c.json(strat)

    # 3. Evaluation Tab
    with tabs[2]:
        st.subheader("Ablation & Evaluation Report")
        report = load_json_cached(str(eval_path))
        if not report:
            st.info(f"No evaluation report found at {eval_path}. Run 'python -m src.evaluate --split dev --dry-run'.")
        else:
            st.write(
                f"**Split:** `{report.get('split')}` ({report.get('num_cases')} cases) | "
                f"**Prompt Hash:** `{report.get('prompt_hash')}`"
            )
            rows = []
            for abl_name, m in report.get("ablations", {}).items():
                rows.append({
                    "Ablation": abl_name,
                    "Precision": m["classifier"]["precision"],
                    "Recall": m["classifier"]["recall"],
                    "F1": m["classifier"]["f1"],
                    "Threat Accuracy": m["analyst"]["threat_accuracy"],
                    "False Alerts": m["false_alerts"],
                    "Invalid Evidence": m["invalid_evidence"],
                    "Parse Failures": m["parse_failures"],
                    "Calls / Event": m.get("avg_llm_calls_per_event", 0),
                    "Tokens / Event": m["avg_tokens_per_event"],
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

            paired = report.get("paired_diff", {})
            if paired:
                st.write(
                    f"**Paired Diff (full vs single_agent):** False Alerts Delta = `{paired.get('false_alerts_diff')}`, "
                    f"Classifier F1 Delta = `{paired.get('classifier_f1_diff')}`"
                )

            st.markdown("### Threat Confusion Matrices")
            for abl_name, m in report.get("ablations", {}).items():
                st.markdown(f"**{abl_name}**")
                cm = m["analyst"]["confusion_matrix"]
                st.dataframe(pd.DataFrame(cm).T, use_container_width=False)

    # 4. Mock Site Control Tab (Live mode only)
    if mode == "Live" and len(tabs) > 3:
        with tabs[3]:
            st.subheader("Mock Site Control (Locus)")
            if not local_flag:
                st.warning("Mock site toggle is restricted to LOCAL_MODE=1 on your local machine.")
            else:
                try:
                    state_resp = requests.get("http://127.0.0.1:5001/state", timeout=2)
                    state_data = state_resp.json()
                    st.json(state_data)
                    if st.button("Toggle Locus AI Feature"):
                        requests.post("http://127.0.0.1:5001/toggle", timeout=2)
                        st.rerun()
                except requests.RequestException as exc:
                    st.error(f"Mock site unreachable on http://127.0.0.1:5001 ({exc}). Start it with 'python mock_sites/app.py'.")


if __name__ == "__main__":
    main()
