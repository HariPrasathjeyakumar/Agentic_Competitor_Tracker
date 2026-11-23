"""Classifier agent: determines whether added text announces a real shipped feature."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from src import PROJECT_ROOT
from src.schemas import ClassifierOutput, parse_json_output

ALLOWED_INPUT_KEYS = ("competitor_name", "added_text")


@dataclass
class AgentResult:
    ok: bool
    output: dict[str, Any] | None
    status: Literal["ok", "parse_failed"]
    provider: str
    model: str
    error: str | None = None
    tokens_approx: int = 0


def _build_prompt(inputs: dict[str, Any], prompts_dir: Path) -> str:
    # Enforce strict information barrier: read ONLY allowed keys.
    competitor_name = str(inputs["competitor_name"])
    added_text = str(inputs["added_text"])

    template = (prompts_dir / "classifier.txt").read_text(encoding="utf-8")
    return (
        template.replace("{competitor_name}", competitor_name)
        .replace("{added_text}", added_text)
    )


def run_classifier(
    llm: Any,
    inputs: dict[str, Any],
    max_retries: int = 1,
    prompts_dir: Path | None = None,
) -> AgentResult:
    """Run the Classifier agent with strict input filtering and 1-retry JSON validation."""
    filtered = {k: inputs[k] for k in ALLOWED_INPUT_KEYS if k in inputs}
    if len(filtered) != len(ALLOWED_INPUT_KEYS):
        missing = [k for k in ALLOWED_INPUT_KEYS if k not in filtered]
        raise ValueError(f"Classifier missing required input keys: {missing}")

    p_dir = prompts_dir if prompts_dir is not None else PROJECT_ROOT / "prompts"
    base_prompt = _build_prompt(filtered, p_dir)

    prompt = base_prompt
    total_tokens = 0
    last_error = ""
    last_provider = ""
    last_model = ""

    for attempt in range(max_retries + 1):
        res = llm.complete(prompt, agent="classifier")
        total_tokens += res.approx_tokens
        last_provider = res.provider
        last_model = res.model
        try:
            parsed = parse_json_output(res.text, ClassifierOutput)
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
