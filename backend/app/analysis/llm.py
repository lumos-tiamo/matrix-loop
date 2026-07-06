from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator


@runtime_checkable
class LLMClient(Protocol):
    def complete(self, *, system: str, prompt: str) -> str: ...


class AnalysisResult(BaseModel):
    positioning_clarity: float
    positioning_label: str
    content_direction: str
    suggested_topics: list[str] = Field(default_factory=list)

    @field_validator("positioning_clarity")
    @classmethod
    def _clamp_clarity(cls, v: float) -> float:
        return max(0.0, min(100.0, float(v)))


_SYSTEM = (
    "You are a social-media account strategist. Analyze the account's positioning "
    "and content direction. Respond with ONLY a JSON object - no prose, no code fences."
)


# NOTE: positioning/topic values are DB-managed today; validate at ingestion if raw scraped content ever feeds these fields.
def _build_prompt(account, content_items) -> str:
    topics = [c.topic for c in content_items if getattr(c, "topic", None)]
    return "\n".join([
        f"Platform: {account.platform}",
        f"Handle: {account.handle}",
        f"Stated positioning: {account.positioning or '(none)'}",
        f"Recent content topics: {topics if topics else '(none)'}",
        "",
        "Return a JSON object with exactly these keys:",
        '{"positioning_clarity": <number 0-100>, "positioning_label": "<short niche>", '
        '"content_direction": "<one-paragraph recommendation>", '
        '"suggested_topics": ["<topic idea>", "..."]}',
    ])


def _extract_json(text: str) -> str:
    end = text.rfind("}")
    if end == -1:
        return text.strip()
    start = text.rfind("{", 0, end)
    if start != -1:
        return text[start:end + 1]
    return text.strip()


def analyze_positioning(account, content_items, client: LLMClient) -> AnalysisResult:
    system = _SYSTEM
    prompt = _build_prompt(account, content_items)
    last_err: Exception | None = None
    for _ in range(2):  # retries parse/validation failures only; transport errors from complete() propagate
        raw = client.complete(system=system, prompt=prompt)
        try:
            return AnalysisResult(**json.loads(_extract_json(raw)))
        except Exception as err:  # noqa: BLE001 - any parse/validation error triggers retry
            last_err = err
    raise ValueError(f"LLM returned unparseable analysis after retry: {last_err}")
