"""Scout module for polite page fetching, text extraction, and timestamped snapshot saving."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
import trafilatura

from src import PROJECT_ROOT, resolve_path

logger = logging.getLogger(__name__)


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip().lower()).strip("_")
    return cleaned or "competitor"


def _can_fetch_robots(url: str, user_agent: str, timeout_seconds: float) -> bool:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False
    robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")
    rp = RobotFileParser()
    try:
        resp = requests.get(
            robots_url,
            headers={"User-Agent": user_agent},
            timeout=min(timeout_seconds, 5.0),
        )
        if resp.status_code == 404 or resp.status_code >= 500:
            return True
        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
            return rp.can_fetch(user_agent, url)
        return True
    except requests.RequestException:
        return True


def fetch_page(url: str, config: dict[str, Any]) -> str | None:
    """Fetch HTML for url honoring robots.txt, configured User-Agent, and timeout."""
    scout_cfg = config.get("scout", {})
    user_agent = str(scout_cfg.get("user_agent", "CompetitorTracker/0.1"))
    timeout_seconds = float(scout_cfg.get("timeout_seconds", 15))
    respect_robots = bool(scout_cfg.get("respect_robots_txt", True))

    if respect_robots and not _can_fetch_robots(url, user_agent, timeout_seconds):
        logger.warning("Blocked by robots.txt: %s", url)
        return None

    try:
        resp = requests.get(url, headers={"User-Agent": user_agent}, timeout=timeout_seconds)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        logger.error("Failed to fetch %s: %s", url, exc)
        return None


def extract_text(html: str) -> str:
    """Extract readable text using trafilatura with BeautifulSoup fallback."""
    if not html:
        return ""
    extracted = trafilatura.extract(html, include_comments=False, include_tables=True)
    if extracted and extracted.strip():
        return extracted.strip()

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    lines = [line.strip() for line in soup.get_text(separator="\n").splitlines()]
    return "\n".join(line for line in lines if line)


def make_scan_id(as_of: date) -> str:
    """Generate a Windows-safe, chronologically sortable timestamped scan ID."""
    now = datetime.now(timezone.utc)
    return f"{as_of.isoformat()}_{now.strftime('%H%M%S_%f')}"


def save_snapshot_text(
    competitor: str,
    page: str,
    as_of: date,
    text: str,
    snapshots_dir: Path | str,
    scan_id: str | None = None,
) -> Path:
    """Save extracted snapshot text under <snapshots_dir>/<slug>/<page>/<scan_id>.md."""
    base = Path(snapshots_dir)
    target_dir = base / slugify(competitor) / slugify(page)
    target_dir.mkdir(parents=True, exist_ok=True)
    stem = scan_id if scan_id else make_scan_id(as_of)
    out_path = target_dir / f"{stem}.md"
    out_path.write_text(text, encoding="utf-8")
    return out_path


def run_scout(
    config: dict[str, Any],
    as_of: date,
    base_dir: Path | None = None,
    scan_id: str | None = None,
) -> list[Path]:
    """Fetch changelog and pricing pages for all configured competitors."""
    root = base_dir if base_dir is not None else PROJECT_ROOT
    snapshots_dir = resolve_path(config, "snapshots_dir", base_dir=root)
    saved_paths: list[Path] = []
    batch_scan_id = scan_id if scan_id else make_scan_id(as_of)

    for comp in config.get("competitors", []):
        name = str(comp["name"])
        for page_name, url_key in (("changelog", "changelog_url"), ("pricing", "pricing_url")):
            url = comp.get(url_key)
            if not url:
                continue
            html = fetch_page(str(url), config)
            if html is None:
                continue
            text = extract_text(html)
            saved = save_snapshot_text(
                competitor=name,
                page=page_name,
                as_of=as_of,
                text=text,
                snapshots_dir=snapshots_dir,
                scan_id=batch_scan_id,
            )
            saved_paths.append(saved)

    return saved_paths
