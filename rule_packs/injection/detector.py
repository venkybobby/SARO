"""Deterministic prompt-injection / system-prompt-leakage detector (STORY-AISEC-001).

Evidence-only and external-model-free. Given prompt/output text, it:
  1. normalizes to defeat obfuscation — strips zero-width chars, drops Unicode
     tag-range codepoints, NFKC-folds, and (bounded) decodes base64 / ROT13;
  2. matches a versioned, SHA-256-hashed heuristic corpus (``pack.yaml``);
  3. returns evidence-shaped findings — never a verdict, never a score.

Ports the deterministic slice of the Apache-2.0 skill
``detecting-indirect-prompt-injection`` (mukul975/Anthropic-Cybersecurity-Skills).
The skill's model-based scanners (Llama Guard, deberta) are intentionally NOT
ported: SARO's core scoring never calls an external model (Non-Negotiable #1).
"""

from __future__ import annotations

import base64
import codecs
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_PACK_ROOT = Path(__file__).parent

# Zero-width and BOM-like joiners used to splice trigger phrases apart.
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)
# Unicode Tags block (U+E0000–U+E007F) — invisible, abused to smuggle text.
_TAG_RANGE = set(range(0xE0000, 0xE0080))
# Long-ish base64-looking tokens; short ones decode to noise.
_B64_TOKEN = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")

# Confusable / homoglyph fold map (STORY-AISEC-005): well-established Cyrillic and
# Greek Latin-lookalikes → their Latin skeleton, so an attacker who swaps
# `ignore` → `іgnоrе` (Cyrillic) cannot evade the rules. Basis: the Unicode
# confusables data (TR39). Deliberately CURATED, not a full transliteration —
# only characters with an unambiguous Latin skeleton are folded, and NO Latin
# codepoint is ever a key (that would corrupt legitimate text). NFKC (applied
# just before this) already folds compatibility variants; this adds the
# script-confusable set NFKC does not touch.
# str.maketrans yields ordinal→ordinal entries (dict[int, int]); str.translate
# accepts that form directly.
_CONFUSABLES: dict[int, int] = {}
# Cyrillic lowercase → Latin
_CONFUSABLES.update(str.maketrans("аеорсхуіјѕкԁһԛѵԝ", "aeopcxyijskdhqvw"))
# Cyrillic uppercase → Latin
_CONFUSABLES.update(str.maketrans("АВЕКМНОРСТХУІЈЅ", "ABEKMHOPCTXYIJS"))
# Greek uppercase → Latin
_CONFUSABLES.update(str.maketrans("ΑΒΕΖΗΙΚΜΝΟΡΤΥΧ", "ABEZHIKMNOPTYX"))
# Greek lowercase (only the unambiguous ones) → Latin
_CONFUSABLES.update(str.maketrans("ονρ", "ovp"))


def _is_texty(s: str) -> bool:
    """True if ``s`` is human-readable text — printable once common whitespace
    (newline/tab/carriage-return) is allowed. ``str.isprintable()`` alone rejects
    any multi-line payload, which would silently drop line-spanning injection
    carriers (reviewer AC-2 gap)."""
    return bool(s.strip()) and all(ch.isprintable() or ch in "\t\n\r" for ch in s)


@dataclass(frozen=True)
class CompiledRule:
    rule_id: str
    title: str
    severity: str
    pattern: "re.Pattern[str]"
    atlas_technique_id: str | None


@dataclass(frozen=True)
class InjectionFinding:
    """One evidence-shaped indicator. The caller PII-redacts ``evidence`` before
    it is persisted or exported (the engine does this via ``_redact_pii``)."""

    rule_id: str
    title: str
    severity: str
    atlas_technique_id: str | None
    matched_on: str  # "raw" | "decoded"
    evidence: str


@dataclass(frozen=True)
class InjectionPack:
    name: str
    version: str
    title: str
    obligation: str
    pack_hash: str
    max_scan_chars: int
    max_decode_depth: int
    min_decoded_len: int
    rules: tuple[CompiledRule, ...]


def _decode_segments(
    text: str, *, max_decode_depth: int, min_decoded_len: int
) -> list[str]:
    """Bounded base64 + ROT13 decode. Returns decoded strings (never re-executed).

    base64 is decoded recursively up to ``max_decode_depth`` (decode-bomb guard).
    ROT13 is an involution, so it is applied exactly once — to the original text
    and to each base64-decoded segment — never recursively (rot13∘rot13 is the
    identity and would just re-report the plaintext as if it were decoded).
    """
    b64_segments: list[str] = []
    frontier = [text]
    for _ in range(max(0, max_decode_depth)):
        nxt: list[str] = []
        for chunk in frontier:
            for token in _B64_TOKEN.findall(chunk):
                try:
                    dec = base64.b64decode(token, validate=True).decode(
                        "utf-8", "ignore"
                    )
                except (ValueError, UnicodeError):
                    continue
                if _is_texty(dec) and len(dec) >= min_decoded_len:
                    b64_segments.append(dec)
                    nxt.append(dec)
        frontier = nxt
        if not frontier:
            break

    out: list[str] = list(b64_segments)
    for chunk in [text, *b64_segments]:
        try:
            rot = codecs.decode(chunk, "rot_13")
        except (ValueError, UnicodeError):
            continue
        if rot and rot != chunk:
            out.append(rot)
    return out


def normalize(
    text: str,
    *,
    max_scan_chars: int = 20_000,
    max_decode_depth: int = 2,
    min_decoded_len: int = 5,
) -> tuple[str, list[str]]:
    """Return ``(base, decoded)``.

    ``base`` is the size-bounded, de-obfuscated original text (zero-width stripped,
    tag-range dropped, NFKC-folded). ``decoded`` is the list of base64/ROT13-decoded
    segments extracted from it, each a candidate carrier of a hidden directive.
    """
    if not text:
        return "", []
    text = text[:max_scan_chars]
    text = text.translate(_ZERO_WIDTH)
    text = "".join(ch for ch in text if ord(ch) not in _TAG_RANGE)
    # NFKC first (compatibility variants), then fold script confusables so
    # Cyrillic/Greek homoglyphs collapse to their Latin skeleton before matching.
    base = unicodedata.normalize("NFKC", text).translate(_CONFUSABLES)
    decoded = _decode_segments(
        base, max_decode_depth=max_decode_depth, min_decoded_len=min_decoded_len
    )
    return base, decoded


def _fragment(hay: str, match: re.Match[str]) -> str:
    """A short window around the match — the caller redacts PII before egress."""
    start = max(0, match.start() - 24)
    end = min(len(hay), match.end() + 24)
    return hay[start:end].strip()


def scan(text: str, pack: InjectionPack) -> list[InjectionFinding]:
    """Detect injection indicators in ``text``. Deterministic, no I/O, no model."""
    base, decoded = normalize(
        text,
        max_scan_chars=pack.max_scan_chars,
        max_decode_depth=pack.max_decode_depth,
        min_decoded_len=pack.min_decoded_len,
    )
    findings: list[InjectionFinding] = []
    seen: set[tuple[str, str]] = set()

    def _match(hay: str, where: str) -> None:
        # Patterns are compiled re.IGNORECASE, so match the original text directly
        # — a separate .lower() can shift match offsets (str.lower() is not always
        # length-preserving) and clip the recorded evidence fragment.
        for rule in pack.rules:
            m = rule.pattern.search(hay)
            if not m:
                continue
            key = (rule.rule_id, where)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                InjectionFinding(
                    rule_id=rule.rule_id,
                    title=rule.title,
                    severity=rule.severity,
                    atlas_technique_id=rule.atlas_technique_id,
                    matched_on=where,
                    evidence=_fragment(hay, m),
                )
            )

    _match(base, "raw")
    for seg in decoded:
        _match(seg, "decoded")
    return findings


def _pack_hash(name: str, version: str, rules: list[dict[str, Any]]) -> str:
    """Deterministic SHA-256 over the pack identity + rule corpus (mirrors the
    engine's ``_compute_rule_pack_hash`` discipline)."""
    payload = {
        "name": name,
        "version": version,
        "rules": sorted(
            (
                {
                    "rule_id": r["rule_id"],
                    "pattern": r["pattern"],
                    "severity": r.get("severity", ""),
                    "atlas": r.get("atlas_technique_id"),
                }
                for r in rules
            ),
            key=lambda r: r["rule_id"],
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def load_injection_pack(version: str = "1.0.0") -> InjectionPack:
    """Load and compile the versioned injection rule-pack."""
    path = _PACK_ROOT / version / "pack.yaml"
    with open(path, encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    norm = raw.get("normalization", {}) or {}
    rules_raw: list[dict[str, Any]] = raw.get("rules", []) or []
    compiled = tuple(
        CompiledRule(
            rule_id=r["rule_id"],
            title=r["title"],
            severity=r.get("severity", "MEDIUM"),
            pattern=re.compile(r["pattern"], re.IGNORECASE),
            atlas_technique_id=r.get("atlas_technique_id"),
        )
        for r in rules_raw
    )
    return InjectionPack(
        name=raw.get("name", "RP-PROMPT-INJECTION"),
        version=str(raw.get("version", version)),
        title=raw.get("title", ""),
        obligation=raw.get("obligation", ""),
        pack_hash=_pack_hash(
            raw.get("name", "RP-PROMPT-INJECTION"),
            str(raw.get("version", version)),
            rules_raw,
        ),
        max_scan_chars=int(norm.get("max_scan_chars", 20_000)),
        max_decode_depth=int(norm.get("max_decode_depth", 2)),
        min_decoded_len=int(norm.get("min_decoded_len", 5)),
        rules=compiled,
    )
