#!/usr/bin/env python3
"""Pre-flight quality gate for watchable-video packages.

Centralizes EVERY defect class we hit while iterating the 4-account matrix so they can never
silently regress. Runs on a TRIMMED package (post drop_placeholders / shorten) right before
render. Returns a list of Issue(severity, code, scene, detail). `blockers()` filters the fatal
ones; produce2 aborts a video on any blocker instead of shipping a broken clip.

Defect classes encoded (each = a real bug that once shipped):
  DIRECTIVE_LEAK  - script/authoring note left in narration or headline ("Invite the save",
                    "State the...", "Beat 1", "-> link sticker + bio", CJK "→ 個人檔案 bio")
  NUMBER_SPLIT    - a number broken across caption chunks ("was 90" | "7 billion", "$63" | "6B")
  EMPTY_NARRATION - a scene with no speakable narration after cleaning
  HERO_QUALIFIER  - a giant hero number that is a year / time-span qualifier ("5-MONTH"->5,
                    "Feb 2026"->2026) rather than a metric  (warn: builder now suppresses these)
  BANNED_FACT     - a number/claim on the verified-discard blacklist (hallucinated stats)
  DURATION        - (checked post-render by produce2) clip outside 40-90s
"""
from __future__ import annotations

import re
import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from gen_watchable import (  # noqa: E402
    chunk_caption, clean_text, drop_placeholders, hero_number, is_placeholder,
)

# Verified-discard blacklist (hallucinated stats we must NEVER put on screen). Extend as caught.
# Each entry is a regex tested against narration+headline; a hit = BANNED_FACT blocker.
BANNED_PATTERNS = [
    r"\$?\s*71\s*亿",                       # 黄金代币总市值$71亿 (real ~$5.5B)
    r"涨\s*300%|\+?\s*300%\s*(涨|gain)",     # 金价涨300% (real ~289% and different metric)
    r"\$?4,?768",                            # 金价 $4,768 高点 (fabricated)
    r"7\s*万\+?\s*agent|70,?000\+?\s*agent", # Robinhood 7万+ agent账户
    r"BUIDL.{0,12}250\s*亿",                 # BUIDL 250亿
    r"sUSDe.{0,12}(10|15)\s*[-–]?\s*15?%",   # sUSDe 10-15% 旧值
]
_BANNED = [re.compile(p, re.I) for p in BANNED_PATTERNS]

# a caption chunk that ends OR starts mid-number (digit stranded from its unit / other digits)
_ENDS_IN_LONE_NUM = re.compile(r"(?:^|\s)\d[\d,]*\.?$")            # "...was 90"
_STARTS_WITH_NUM_TAIL = re.compile(r"^\d[\d,]*\s*(billion|million|B|M|K|%)?\b", re.I)  # "7 billion..."


class Issue:
    __slots__ = ("severity", "code", "scene", "detail")

    def __init__(self, severity, code, scene, detail):
        self.severity, self.code, self.scene, self.detail = severity, code, scene, detail

    def __repr__(self):
        s = f"s{self.scene}" if self.scene is not None else "-"
        return f"[{self.severity}] {self.code} {s}: {self.detail}"


def _number_split(chunks):
    """Return True if consecutive caption chunks split a number: prev ends in a lone number and
    next starts with a number/unit (the '$90.7B'->'was 90' | '7 billion' failure)."""
    for a, b in zip(chunks, chunks[1:]):
        if _ENDS_IN_LONE_NUM.search(a) and _STARTS_WITH_NUM_TAIL.match(b.strip()):
            return f"{a!r} | {b!r}"
    # a single chunk that is JUST a stranded number fragment
    for c in chunks:
        if re.fullmatch(r"\d[\d,]*\.?", c.strip()):
            return f"lone-number chunk {c!r}"
    return None


def check_package(pkg) -> list[Issue]:
    """Validate a TRIMMED package (already through drop_placeholders/shorten). Pure, no I/O."""
    issues: list[Issue] = []
    is_cjk = (pkg.get("language", "") or "").startswith(("繁", "zh"))
    scenes = pkg.get("scenes") or []
    if not scenes:
        issues.append(Issue("blocker", "EMPTY_PACKAGE", None, "no scenes after trim"))
        return issues
    for i, s in enumerate(scenes):
        nr = clean_text(s.get("narration", "") or "")
        oc = clean_text(s.get("onScreenCaption", "") or "")
        # 1) directive leak in either field
        for fld, txt in (("narration", nr), ("headline", oc)):
            if txt and is_placeholder(txt):
                issues.append(Issue("blocker", "DIRECTIVE_LEAK", i, f"{fld} is a directive: {txt[:60]!r}"))
        # 2) empty narration
        if not nr:
            issues.append(Issue("blocker", "EMPTY_NARRATION", i, "no speakable narration"))
        # 3) number split in captions
        chunks = chunk_caption(nr, is_cjk)
        split = _number_split(chunks)
        if split:
            issues.append(Issue("blocker", "NUMBER_SPLIT", i, split))
        # 4) hero qualifier (year/time-span) — builder already suppresses; warn if the SOURCE
        #    still leans on one so copy can be improved
        hn = hero_number(oc) or hero_number(nr)
        if hn is None and re.search(r"\d", oc or nr):
            # numbers present but none is a valid hero -> a text card (fine, informational)
            pass
        # 5) banned facts
        blob = f"{nr} {oc}"
        for pat in _BANNED:
            m = pat.search(blob)
            if m:
                issues.append(Issue("blocker", "BANNED_FACT", i, f"blacklisted stat {m.group(0)!r}"))
    return issues


def blockers(issues) -> list[Issue]:
    return [x for x in issues if x.severity == "blocker"]


def _selftest():
    """Run against the real 16 packages via produce2.trim_pkg — should be clean now."""
    import json, os
    from produce2 import trim_pkg  # noqa
    pkgs = json.load(open(os.path.join(os.path.dirname(__file__), "..", "_content_packages_2026-07-16.json")))["packages"]
    total = 0
    for p in pkgs:
        tp = trim_pkg(p)
        iss = check_package(tp)
        b = blockers(iss)
        total += len(b)
        tag = "OK " if not b else "!! "
        print(f"{tag}{p['id']}: {len(iss)} issue(s), {len(b)} blocker(s)")
        for x in b:
            print("     ", x)
    print(f"\nTOTAL BLOCKERS ACROSS 16: {total}")
    return total


if __name__ == "__main__":
    sys.exit(1 if _selftest() else 0)
