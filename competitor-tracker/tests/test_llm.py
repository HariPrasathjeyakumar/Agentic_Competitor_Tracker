"""Tests for src/llm.py caching, backoff, fallback, and key checks."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src import load_config
from src.llm import LLMClient


def _make_test_config(tmp_path: Path) -> dict:
    cfg = load_config()
    cfg["paths"]["cache_dir"] = str(tmp_path / "cache")
    cfg["paths"]["logs_dir"] = str(tmp_path / "logs")
    cfg["llm"]["max_tries"] = 3
    cfg["llm"]["backoff_base_seconds"] = 1
    cfg["llm"]["backoff_max_seconds"] = 4
    return cfg


def test_missing_both_keys_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    cfg = _make_test_config(tmp_path)
    with pytest.raises(RuntimeError, match="No LLM API keys configured"):
        LLMClient(config=cfg, base_dir=tmp_path)


def test_cache_miss_then_hit_calls_provider_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    cfg = _make_test_config(tmp_path)

    mock_gemini = MagicMock()
    mock_gemini.models.generate_content.return_value = SimpleNamespace(text='{"ok": true}')

    monkeypatch.setattr(LLMClient, "_build_gemini_client", lambda self, key: mock_gemini)
    client = LLMClient(config=cfg, base_dir=tmp_path)

    res1 = client.complete("Classify this feature launch", agent="classifier")
    assert res1.cached is False
    assert res1.calls_made == 1
    assert res1.text == '{"ok": true}'
    assert mock_gemini.models.generate_content.call_count == 1

    res2 = client.complete("Classify this feature launch", agent="classifier")
    assert res2.cached is True
    assert res2.calls_made == 0
    assert res2.text == '{"ok": true}'
    assert mock_gemini.models.generate_content.call_count == 1


def test_backoff_triggered_on_429(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    cfg = _make_test_config(tmp_path)

    attempts = {"count": 0}

    def flaky_generate(**kwargs):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("429 RESOURCE_EXHAUSTED: rate limit")
        return SimpleNamespace(text='{"recovered": true}')

    mock_gemini = MagicMock()
    mock_gemini.models.generate_content.side_effect = flaky_generate
    monkeypatch.setattr(LLMClient, "_build_gemini_client", lambda self, key: mock_gemini)

    sleep_calls: list[float] = []
    monkeypatch.setattr("src.llm.time.sleep", lambda s: sleep_calls.append(s))

    client = LLMClient(config=cfg, base_dir=tmp_path)
    res = client.complete("Rate limited prompt", agent="analyst")
    assert res.text == '{"recovered": true}'
    assert len(sleep_calls) == 2
    assert all(s >= 1.0 for s in sleep_calls)
