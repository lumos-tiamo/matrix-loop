from __future__ import annotations

_SYSTEM = (
    "You are a senior short-form crypto/finance scriptwriter for ONE branded account in a "
    "private-traffic matrix. You write SHARP, SPECIFIC, publish-ready spoken scripts — never "
    "generic evergreen filler. Hard rules:\n"
    "1. Open with a 3-second HOOK built on a specific fact, number, dated event, or contrarian "
    "claim — never a vague premise.\n"
    "2. Every beat carries a CONCRETE detail: a real number, a named protocol/event, a date, or a "
    "precise mechanism. Use ONLY numbers/facts given in the topic/trends — if none are given, stay "
    "concrete about the mechanism/angle but INVENT NO statistics, prices, dates, or percentages.\n"
    "3. This narration is the VOICEOVER layer: it will be auto-split into ~6 short scenes with "
    "rolling captions and moving data visuals. Write punchy, front-loaded sentences — put the key "
    "number/claim FIRST in each sentence. 5-7 short sentences total.\n"
    "3b. Write numbers as DIGITS, not spelled-out words: '138,000' not 'one hundred thirty-eight "
    "thousand'; '$63.6B', '4.5%', '289,000', 'July 22, 2026'. Digits read as data and drive the "
    "on-screen number animation.\n"
    "4. Match the channel's brand voice + niche. End with ONE soft, on-brand CTA (follow / link in "
    "bio) — no hard sell.\n"
    "5. Compliance: information/education only, NOT investment advice; NEVER promise returns. "
    "For Traditional-Chinese (Taiwan) channels, keep any legal/penalty framing careful and separate.\n"
    "BANNED phrases: 'stay ahead of the curve', 'in today's fast-paced world', 'operational hygiene', "
    "'game-changer', 'unlock', 'dive in', and any hollow filler. If you cannot be specific, be shorter.\n"
    "Output ONLY the spoken script text — no headings, no scene labels, no notes."
)


def build_script_prompt(topic: str, brief, performance: str | None = None, trends: str | None = None) -> str:
    secs = int(getattr(brief, "target_seconds", None) or 50)
    words = round(secs * 2.7)
    lang = getattr(brief, "language", None) or "en"
    is_cjk = str(lang).startswith(("繁", "zh"))
    lines = [
        f"Channel main direction: {getattr(brief, 'main_direction', '')}",
        f"Sub-niches: {'、'.join(getattr(brief, 'sub_niches', None) or []) or '(none)'}",
        f"Host persona: {getattr(brief, 'persona', None) or '(faceless voiceover)'}",
        f"Tone: {getattr(brief, 'tone', None) or 'clear, sharp, credible'}",
        f"Language: {lang}" + ("  (write the script in Traditional Chinese)" if is_cjk else ""),
        "",
        f"TOPIC (the specific angle for THIS video): {topic}",
        f"Target length: a ~{secs}-second spoken script (~{words} words). Match this length; do not pad.",
        "",
        "Write the sharpest version of this exact topic: lead with its most specific hook, hang each "
        "sentence on a concrete detail, and land one clear takeaway before the CTA. If the topic is "
        "vague, narrow it to the single most concrete, current angle you can defend — do not drift "
        "into generic advice.",
    ]
    if trends:
        lines += ["", "CURRENT DATA / TRENDS to ground this script (cite the concrete numbers/events "
                  "verbatim; do not alter them):", trends]
    if performance:
        lines += ["", performance]
    return "\n".join(lines)


# High-conversion format variants (from the benchmark accounts). Inject to reframe a topic into a
# format that drives trust/engagement — @zachxbt-style scam warnings, @CryptoDonAlt-style loss posts,
# personal-result posts, IG myth-busting, TikTok "AI did it for me" reveals.
ANGLES = {
    "fake_checker_warning": (
        "FORMAT = 🚨 scam/safety WARNING (builds trust like @zachxbt): reframe around how a fake "
        "claim-checker / airdrop page drains wallets when you sign an approval. Explain the exact "
        "mechanism (sign = approve a drainer, not a transfer), 2-3 red flags to spot it, and what to "
        "verify before signing. Open with the warning, not the topic."),
    "personal_result": (
        "FORMAT = first-person result: 'here's what actually happened when I did this' — a concrete, "
        "honest outcome with real numbers and ONE repeatable step. Not shilling; show the real math."),
    "loss_review": (
        "FORMAT = honest trade post-mortem (builds trust like @CryptoDonAlt): show a REAL setup, the "
        "invalidation level that hit, the loss (-X% / -$Y), and the one lesson. Credibility over flex."),
    "myth_bust": (
        "FORMAT = myth-busting side-by-side (IG style): 'X vs Y' with the real numbers compared "
        "directly (e.g. on-chain yield vs bank interest), then the honest takeaway."),
    "ai_reveal": (
        "FORMAT = 'I asked the AI (Nina) and here's what it found' reveal: frame the topic as something "
        "Nina checked/explained for you in one line, showing the AI assist naturally."),
}


def generate_script(topic: str, brief, client, performance: str | None = None,
                    trends: str | None = None, angle: str | None = None) -> str:
    prompt = build_script_prompt(topic, brief, performance, trends)
    if angle and angle in ANGLES:
        prompt += "\n\n" + ANGLES[angle]
    return client.complete(system=_SYSTEM, prompt=prompt).strip()
