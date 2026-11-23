# Competitor Tracker

Competitor Tracker is a multi-agent competitive-intelligence pipeline that monitors competitor changelog and pricing pages, isolates meaningful product updates with deterministic timestamped diffs, and enforces strict code-level information barriers across three LLM agents (`Classifier`, `Analyst`, and `Strategist`) guarded by a verbatim `Evidence check` and atomic `Scribe` logging. Every decision—including dismissed noise, invalid quotes, and schema validation failures—is recorded in a structured JSON feed and benchmarked across ablations (`full`, `no_classifier`, `single_agent`).

## Agent Access & Information Barriers

| Agent | Type | Reads (access) | Must NOT see | Writes (output) | Sends to |
|---|---|---|---|---|---|
| Scout | Code | Competitor URLs from config | Anything from other agents | Timestamped snapshot file per page scan | Diff-Engine |
| Diff-Engine | Code | Two snapshots: newest and previous scan for the same page | Product data, LLM output | DiffEvent (added text only), or None | Classifier |
| Classifier | LLM | Added text, competitor name | Product description, key features, roadmap, full snapshot | ClassifierOutput JSON | Pipeline: stops the event if not a launch |
| Analyst | LLM | Classifier output, competitor name, product description, key features, added text | Full snapshot, Strategist output | AnalystOutput JSON | Evidence check |
| Evidence check | Code | Analyst's evidence_quote, full snapshot text | Everything else | Pass, or status "invalid_evidence" | Strategist (only if pass) |
| Strategist | LLM | Analyst JSON output, product description | Raw snapshot, added text | StrategistOutput JSON (may contest Analyst) | Scribe |
| Scribe | Code | Full event record from all agents | Nothing is filtered | Appended feed entry, stdout digest | Feed file, Streamlit UI |

## Windows PowerShell Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Add GEMINI_API_KEY and/or GROQ_API_KEY (and LOCAL_MODE=1 on your local machine) to .env
```

## Run Order & Reproducible Day 1 / Day 9 Demo

```powershell
python -m src.dataset
python -m src.evaluate --split dev --dry-run
# Terminal 1:
python mock_sites/app.py
# Terminal 2:
streamlit run app.py
# Terminal 3 (Day 1 baseline -> Toggle feature on -> Day 9 detection):
python -m src.pipeline --as-of 2026-11-15
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5001/toggle
python -m src.pipeline --as-of 2026-11-23
```

Because Scout writes timestamped scan IDs (`<YYYY-MM-DD>_<HHMMSS_ffffff>.md`) and Diff-Engine compares each scan against the immediately preceding scan with `min_diff_chars: 60`, same-day reruns never overwrite earlier scans and concise launches still reach the Classifier.

## Running Tests

```powershell
pytest -v
```

## Evaluation Methodology

- **Dev Split (`--split dev`)**: Used freely during prompt engineering on the 60% stratified development slice (`data/labels/dev.json`).
- **Locked Held-Out Split (`--split heldout --final`)**: Protected by a three-layer lock: `evaluation.held_out_locked: true` in `config.yaml`, mandatory `--final` CLI flag, and an atomic `data/labels/heldout_used.flag` file created after the single allowed run to block subsequent executions.
- **Ablations**:
  - `full`: Complete information-barriered pipeline (`Classifier` -> `Analyst` -> `Evidence check` -> `Strategist`).
  - `no_classifier`: Skips `Classifier`, sending every diff >= `min_diff_chars` directly to `Analyst` to measure false-alert inflation.
  - `single_agent`: Collapses `Classifier`, `Analyst`, and `Strategist` into one `prompts/single_agent.txt` call (still gated by verbatim `Evidence check`) to quantify multi-agent isolation gains.

## Deployment

Deploy on **Streamlit Community Cloud** in **Replay** mode using the committed `data/feed.json`, `data/eval_report.json`, and `data/eval_report.md` artifacts. API keys and `LOCAL_MODE=1` are never required in cloud Replay deployments.

## Limitations

- Uses a synthetic 40-case labeled dataset rather than external live SaaS historical archives.
- Monitors local mock Flask competitor sites by default rather than scraping third-party production websites.
- Subject to free-tier Gemini and Groq rate limits and daily quotas when run live.
- Extracts static HTML text via `trafilatura` / `BeautifulSoup` without headless-browser JavaScript rendering.
