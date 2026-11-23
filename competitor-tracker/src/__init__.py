"""Competitor Tracker multi-agent competitive intelligence package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load YAML configuration from config.yaml."""
    path = Path(config_path) if config_path is not None else PROJECT_ROOT / "config.yaml"
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid configuration structure in {path}")
    return data


def resolve_path(config: dict[str, Any], path_key: str, base_dir: Path | None = None) -> Path:
    """Resolve a configured path relative to the project root or provided base directory."""
    root = base_dir if base_dir is not None else PROJECT_ROOT
    raw = config.get("paths", {}).get(path_key)
    if not raw:
        raise KeyError(f"Missing path key '{path_key}' in config.yaml")
    p = Path(raw)
    return p if p.is_absolute() else root / p
