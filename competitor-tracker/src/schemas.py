"""Pydantic v2 schemas and strict JSON parser for agent outputs."""

from __future__ import annotations

import json
import re
from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

T = TypeVar("T", bound=BaseModel)


class ClassifierOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_feature_launch: StrictBool
    category: Literal["new_feature", "bug_fix", "cosmetic", "blog_noise", "pricing_change"]
    feature_name: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("feature_name")
    @classmethod
    def clean_feature_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None


class AnalystOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threat_level: Literal["HIGH", "MEDIUM", "LOW"]
    reasoning: str = Field(min_length=20)
    evidence_quote: str = Field(min_length=15, max_length=200)
    overlaps_roadmap_item: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("reasoning")
    @classmethod
    def check_reasoning_sentences(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 20:
            raise ValueError("reasoning must be at least 20 characters")
        parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if len(s.strip()) >= 3]
        if not (2 <= len(parts) <= 4):
            raise ValueError(f"reasoning must contain 2 to 4 sentences (got {len(parts)})")
        return cleaned

    @field_validator("evidence_quote")
    @classmethod
    def check_evidence_quote(cls, v: str) -> str:
        stripped = v.strip()
        if not (15 <= len(stripped) <= 200):
            raise ValueError("evidence_quote must be between 15 and 200 characters")
        return stripped

    @field_validator("overlaps_roadmap_item")
    @classmethod
    def clean_overlap(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None


class StrategistOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: Literal["match", "differentiate", "ignore", "monitor"]
    actions: list[str] = Field(min_length=1, max_length=4)
    contests_analyst: StrictBool
    contest_reason: str | None = None

    @field_validator("actions")
    @classmethod
    def check_actions_non_empty(cls, v: list[str]) -> list[str]:
        cleaned = [item.strip() for item in v if isinstance(item, str) and item.strip()]
        if not (1 <= len(cleaned) <= 4):
            raise ValueError("actions must contain 1 to 4 non-empty strings")
        return cleaned

    @model_validator(mode="after")
    def validate_contest_reason(self) -> "StrategistOutput":
        if self.contests_analyst:
            if not self.contest_reason or not self.contest_reason.strip():
                raise ValueError("contest_reason must be a non-empty string when contests_analyst is true")
            self.contest_reason = self.contest_reason.strip()
        else:
            if self.contest_reason is not None and not self.contest_reason.strip():
                self.contest_reason = None
        return self


class SingleAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classifier: ClassifierOutput
    analyst: AnalystOutput
    strategist: StrategistOutput


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", stripped, flags=re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    return stripped


def parse_json_output(raw_text: str, model_cls: type[T]) -> T:
    """Extract the first JSON object from raw LLM text and validate against model_cls."""
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ValueError("Empty LLM output; expected a JSON object")

    cleaned = _strip_code_fences(raw_text)
    start_idx = cleaned.find("{")
    if start_idx == -1:
        raise ValueError("No JSON object opening brace '{' found in output")

    decoder = json.JSONDecoder()
    try:
        parsed_obj, _ = decoder.raw_decode(cleaned, start_idx)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON: {exc}") from exc

    if not isinstance(parsed_obj, dict):
        raise ValueError("Decoded JSON root must be an object")

    try:
        return model_cls.model_validate(parsed_obj)
    except Exception as exc:
        raise ValueError(f"Schema validation failed: {exc}") from exc
