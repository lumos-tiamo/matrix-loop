from __future__ import annotations

import json

_SYSTEM = "You classify a social account's audience into given segment tags. Respond ONLY with JSON."


def classify_audience(account, content_items, client, candidate_labels: list[str]) -> list[str]:
    topics = [c.topic for c in content_items if getattr(c, "topic", None)]
    prompt = "\n".join([
        f"Account: {account.handle} ({account.platform})",
        f"Positioning: {account.positioning or '(none)'}",
        f"Recent topics: {topics if topics else '(none)'}",
        f"Candidate audience segments: {candidate_labels}",
        'Return JSON {"segments": ["<label from candidates>", ...]} - only labels from the candidate list that fit.',
    ])
    raw = client.complete(system=_SYSTEM, prompt=prompt)
    start, end = raw.find("{"), raw.rfind("}")
    data = json.loads(raw[start:end + 1]) if start != -1 and end != -1 else {}
    picked = data.get("segments", []) if isinstance(data, dict) else []
    allowed = set(candidate_labels)
    return [s for s in picked if s in allowed]
