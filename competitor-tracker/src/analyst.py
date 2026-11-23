"""Analyst agent: assesses threat level and extracts verbatim evidence quote."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src import PROJECT_ROOT
from src.classifier import AgentResult
from src.schemas import AnalystOutput, parse_json_output

ALLOWED_INPUT_KEYS = (
    "competitor_name",
    "product_name",
    "product_description",
    "key_features",
    "classification_json",
    "added_text",
)


def _format_key_features(raw: Any) -> str:
    if isinstance(raw, list):
        return "\n".join(f"- {item}" for item in raw)
    return str(raw)


def _build_prompt(inputs: dict[str, Any], prompts_dir: Path) -> str:
    # Enforce strict information barrier: read ONLY allowed keys.
    classification_val = inputs["classification_json"]
    if not isinstance(classification_val, str):
        classification_val = json.dumps(classification_val, ensure_ascii=False)

    template = (prompts_dir / "analyst.txt").read_text(encoding="utf-8")
    return (
        template.replace("{competitor_name}", str(inputs["competitor_name"]))
        .replace("{product_name}", str(inputs["product_name"]))
        .replace("{product_description}", str(inputs["product_description"]))
        .replace("{key_features}", _format_key_features(inputs["key_features"]))
        .replace("{classification_json}", classification_val)
        .replace("{added_text}", str(inputs["added_text"]))
    )


def run_analyst(
    llm: Any,
    inputs: dict[str, Any],
    max_retries: int = 1,
    prompts_dir: Path | None = None,
) -> AgentResult:
    """Run the Analyst agent with strict input filtering and 1-retry JSON validation."""
    filtered = {k: inputs[k] for k in ALLOWED_INPUT_KEYS if k in inputs}
    if len(filtered) != len(ALLOWED_INPUT_KEYS):
        missing = [k for k in ALLOWED_INPUT_KEYS if k not in filtered]
        raise ValueError(f"Analyst missing required input keys: {missing}")

    p_dir = prompts_dir if prompts_dir is not None else PROJECT_ROOT / "prompts"
    base_prompt = _build_prompt(filtered, p_dir)

    prompt = base_prompt
    total_tokens = 0
    last_error = ""
    last_provider = ""
    last_model = ""

    for attempt in range(max_retries + 1):
        res = llm.complete(prompt, agent="analyst")
        total_tokens += res.approx_tokens
        last_provider = res.provider
        last_model = res.model
        try:
            parsed = parse_json_output(res.text, AnalystOutput)
            return AgentResult(
                ok=True,
                output=parsed.model_dump(),
                status="ok",
                provider=last_provider,
                model=last_model,
                error=None,
                tokens_approx=total_tokens,
            )
        except ValueError as exc:
            last_error = str(exc)
            if attempt < max_retries:
                prompt = (
                    f"{base_prompt}\n\n"
                    f"Your previous output was invalid: {last_error}. Return ONLY valid JSON."
                )

    return AgentResult(
        ok=False,
        output=None,
        status="parse_failed",
        provider=last_provider,
        model=last_model,
        error=last_error,
        tokens_approx=total_tokens,
    )
