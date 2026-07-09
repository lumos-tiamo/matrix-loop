from __future__ import annotations

_SYSTEM = (
    "You are a short-form video scriptwriter for a faceless explainer channel. "
    "Write a tight 45-60 second spoken script: a strong hook, 2-3 concrete points, "
    "and a soft call-to-follow. Output ONLY the script text, no headings or notes."
)


def build_script_prompt(topic: str, brief, performance: str | None = None, trends: str | None = None) -> str:
    lines = [
        f"Channel main direction: {getattr(brief, 'main_direction', '')}",
        f"Sub-niches: {'、'.join(getattr(brief, 'sub_niches', None) or []) or '(none)'}",
        f"Host persona: {getattr(brief, 'persona', None) or '(faceless voiceover)'}",
        f"Tone: {getattr(brief, 'tone', None) or 'clear and energetic'}",
        f"Language: {getattr(brief, 'language', None) or 'en'}",
        f"Topic for this video: {topic}",
        "",
        "Compliance: frame as information/education only, NOT investment advice or a "
        "trading solicitation. Avoid promises of returns.",
    ]
    if trends:
        lines += ["", trends]
    if performance:
        lines += ["", performance]
    return "\n".join(lines)


def generate_script(topic: str, brief, client, performance: str | None = None, trends: str | None = None) -> str:
    return client.complete(system=_SYSTEM,
                           prompt=build_script_prompt(topic, brief, performance, trends)).strip()
