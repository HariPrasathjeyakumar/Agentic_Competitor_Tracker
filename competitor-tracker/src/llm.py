"""Single LLM wrapper with disk caching, exponential backoff, fallback, and deterministic fake."""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from src import PROJECT_ROOT, load_config, resolve_path

_PLACEHOLDER_VALUES = {
    "",
    "your_gemini_key_here",
    "your_groq_key_here",
    "MY_GEMINI_API_KEY",
}


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    cached: bool
    calls_made: int
    approx_tokens: int


def _is_valid_key(value: str | None) -> bool:
    if not value:
        return False
    return value.strip() not in _PLACEHOLDER_VALUES


def _is_rate_limit_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        token in msg
        for token in ("429", "resource_exhausted", "resource exhausted", "rate limit", "too many requests")
    )


def _is_daily_quota_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(token in msg for token in ("daily", "quota exceeded", "quota_exceeded", "per day", "billing"))


class LLMClient:
    """Unified Gemini-primary, Groq-fallback LLM client with SHA-256 disk caching."""

    def __init__(self, config: dict[str, Any] | None = None, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir if base_dir is not None else PROJECT_ROOT
        self.config = config if config is not None else load_config(self.base_dir / "config.yaml")

        env_path = self.base_dir / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)

        self.llm_cfg = self.config.get("llm", {})
        self.primary_cfg = self.llm_cfg.get("primary", {})
        self.fallback_cfg = self.llm_cfg.get("fallback", {})
        self.max_tries = int(self.llm_cfg.get("max_tries", 6))
        self.backoff_base = float(self.llm_cfg.get("backoff_base_seconds", 2))
        self.backoff_max = float(self.llm_cfg.get("backoff_max_seconds", 60))
        self.timeout_seconds = float(self.config.get("scout", {}).get("timeout_seconds", 15))

        self.cache_dir = resolve_path(self.config, "cache_dir", base_dir=self.base_dir)
        self.logs_dir = resolve_path(self.config, "logs_dir", base_dir=self.base_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.calls_made = 0
        self.clients: dict[str, Any] = {}

        gemini_key = os.environ.get("GEMINI_API_KEY")
        groq_key = os.environ.get("GROQ_API_KEY")

        if _is_valid_key(gemini_key):
            self.clients["gemini"] = self._build_gemini_client(gemini_key.strip())
        if _is_valid_key(groq_key):
            self.clients["groq"] = self._build_groq_client(groq_key.strip())

        if not self.clients:
            raise RuntimeError(
                "No LLM API keys configured. Set GEMINI_API_KEY and/or GROQ_API_KEY in .env."
            )

    def _build_gemini_client(self, api_key: str) -> Any:
        from google import genai

        return genai.Client(
            api_key=api_key,
            http_options={"timeout": int(self.timeout_seconds * 1000)},
        )

    def _build_groq_client(self, api_key: str) -> Any:
        from groq import Groq

        return Groq(api_key=api_key, timeout=self.timeout_seconds)

    @staticmethod
    def _cache_key(provider: str, model: str, temperature: float | int, prompt: str) -> str:
        payload = f"{provider}|{model}|{temperature}|{prompt}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _log_line(self, message: str) -> None:
        log_file = self.logs_dir / "llm.log"
        ts = datetime.now(timezone.utc).isoformat()
        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(f"{ts} | {message}\n")

    def _call_provider(self, provider: str, model: str, temperature: float, prompt: str) -> str:
        client = self.clients[provider]
        if provider == "gemini":
            from google.genai import types

            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=temperature),
            )
            text = getattr(response, "text", None)
            if text is None:
                raise RuntimeError("Gemini returned empty response text")
            return str(text)

        if provider == "groq":
            response = client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
                timeout=self.timeout_seconds,
            )
            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("Groq returned empty response content")
            return str(content)

        raise ValueError(f"Unsupported provider: {provider}")

    def _run_with_backoff(self, provider: str, model: str, temperature: float, prompt: str) -> str:
        last_exc: Exception | None = None
        for attempt in range(self.max_tries):
            try:
                return self._call_provider(provider, model, temperature, prompt)
            except Exception as exc:
                last_exc = exc
                if _is_daily_quota_error(exc):
                    raise
                if _is_rate_limit_error(exc) and attempt < self.max_tries - 1:
                    delay = min(self.backoff_max, self.backoff_base * (2**attempt)) + random.uniform(0.0, 1.0)
                    self._log_line(f"backoff | provider={provider} | model={model} | attempt={attempt + 1} | sleep={delay:.2f}s")
                    time.sleep(delay)
                    continue
                if attempt < self.max_tries - 1:
                    delay = min(self.backoff_max, self.backoff_base * (2**attempt))
                    time.sleep(delay)
                    continue
                raise
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"Provider {provider} failed without exception details")

    def complete(self, prompt: str, agent: str) -> LLMResult:
        candidates: list[dict[str, Any]] = []
        if self.primary_cfg.get("provider") in self.clients:
            candidates.append(self.primary_cfg)
        if self.fallback_cfg.get("provider") in self.clients:
            candidates.append(self.fallback_cfg)

        if not candidates:
            raise RuntimeError("No available LLM provider configured for this request.")

        last_error: Exception | None = None
        for idx, spec in enumerate(candidates):
            provider = str(spec["provider"])
            model = str(spec["model"])
            temperature = float(spec.get("temperature", 0))
            key = self._cache_key(provider, model, temperature, prompt)
            c_path = self._cache_path(key)

            if c_path.exists():
                cached_data = json.loads(c_path.read_text(encoding="utf-8"))
                text = str(cached_data["text"])
                approx_tokens = len(prompt + text) // 4
                self._log_line(f"agent={agent} | provider={provider} | model={model} | cached=True")
                return LLMResult(
                    text=text,
                    provider=provider,
                    model=model,
                    cached=True,
                    calls_made=0,
                    approx_tokens=approx_tokens,
                )

            try:
                text = self._run_with_backoff(provider, model, temperature, prompt)
                self.calls_made += 1
                approx_tokens = len(prompt + text) // 4
                c_path.write_text(
                    json.dumps({"provider": provider, "model": model, "text": text}, ensure_ascii=False),
                    encoding="utf-8",
                )
                self._log_line(f"agent={agent} | provider={provider} | model={model} | cached=False")
                return LLMResult(
                    text=text,
                    provider=provider,
                    model=model,
                    cached=False,
                    calls_made=1,
                    approx_tokens=approx_tokens,
                )
            except Exception as exc:
                last_error = exc
                if idx + 1 < len(candidates):
                    next_provider = candidates[idx + 1]["provider"]
                    self._log_line(
                        f"fallback_switch | agent={agent} | from={provider} | to={next_provider} | reason={type(exc).__name__}"
                    )
                    continue
                raise

        if last_error is not None:
            raise last_error
        raise RuntimeError("LLM completion failed across all configured providers")


class FakeLLMClient:
    """Deterministic fake LLM client for tests and dry-run pipeline/evaluation runs."""

    def __init__(
        self,
        responses: dict[str, Any] | Callable[[str, str], str] | None = None,
        provider: str = "fake",
        model: str = "fake-deterministic",
    ) -> None:
        self.responses = responses if responses is not None else {}
        self.provider = provider
        self.model = model
        self.calls_made = 0
        self.history: list[dict[str, str]] = []

    def complete(self, prompt: str, agent: str) -> LLMResult:
        self.calls_made += 1
        self.history.append({"agent": agent, "prompt": prompt})

        if callable(self.responses):
            text = self.responses(prompt, agent)
        else:
            entry = self.responses.get(agent)
            if isinstance(entry, list):
                if not entry:
                    raise RuntimeError(f"FakeLLMClient ran out of queued responses for agent '{agent}'")
                text = entry.pop(0)
            elif callable(entry):
                text = entry(prompt, agent)
            elif isinstance(entry, str):
                text = entry
            elif isinstance(entry, dict):
                text = json.dumps(entry)
            else:
                text = "{}"

        approx_tokens = len(prompt + text) // 4
        return LLMResult(
            text=text,
            provider=self.provider,
            model=self.model,
            cached=False,
            calls_made=1,
            approx_tokens=approx_tokens,
        )
