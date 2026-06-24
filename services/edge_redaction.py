"""STORY-403 (Epic 14): edge-redaction reference component (Safe Harbor, rule-based).

SummitCare operates redaction at its edge; SARO ships this *reference* component +
policy-as-code so the logic isn't duplicated, and so SARO mostly never holds raw PHI.

Design constraints (Epic 14 invariants):
- Deterministic, rule/pattern-based ONLY. No external model/network call. If a local
  NER pass is added later it must stay local — never an external API.
- **No hardcoded master list inside SARO.** The HIPAA-18 identifier patterns live in a
  caller-supplied *data-classification catalog* (a list of FieldClass). Adding/removing
  a field class changes behavior with no code change. SARO provides mechanism, not the list.
- Anti-overclaim (ADR-004): SLIs describe what was *measured against the catalog* (coverage,
  residual rate, drift), never an assertion that PHI was removed.

**SLI honesty (read before trusting `coverage`).** Coverage and residual rate are measured
*only against catalog-expressible patterns*. They are NOT a measure of total PHI removal: free-text
PHI that no catalog pattern can express (e.g. a name in prose) survives and is invisible to the
residual re-scan. `coverage is None` (with `identifiers_redacted == 0`) means "no catalog-detectable
identifiers were present" — a no-signal state, not "PHI-free".

**Catalog trust / ReDoS.** Catalog patterns are operator-supplied policy-as-code, treated as
semi-trusted. `validate_catalog` rejects over-long patterns and obvious catastrophic-backtracking
shapes, but Python's `re` engine is not linear-time — production deployments handling untrusted
catalogs should swap in a linear-time engine (e.g. google-re2) and/or a wall-clock budget.

The component is stateless: it returns a de-identified deep copy and retains nothing of the
original. Expert Determination is a named extension point that raises cleanly rather than
silently passing data through.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, NoReturn

# Placeholder substituted for a detected identifier. Deliberately content-free and chosen so
# it cannot itself match a typical identifier pattern (residual is measured on the original, not
# the output, but a non-matching token is a second line of defence).
_PLACEHOLDER = "[REDACTED]"

# Catalog-trust guards (see module docstring — partial ReDoS mitigation, not a full solution).
MAX_PATTERN_LENGTH = 500
_NESTED_QUANTIFIER = re.compile(r"\([^)]*[+*][^)]*\)\s*[*+]")


@dataclass
class FieldClass:
    """One data-classification entry, injected by the caller (not baked into SARO).

    kind="regex": `pattern` is scanned across free text / string field values.
    kind="field": `field_name` names a structured field redacted wholesale.
    """

    name: str
    hipaa_category: int  # 1..18 (Safe Harbor identifier class)
    kind: str  # "regex" | "field"
    pattern: str | None = None
    field_name: str | None = None
    enabled: bool = True


@dataclass
class RedactionSLI:
    """Per-batch service-level indicators — measured against the catalog, not asserted (ADR-004).

    coverage/residual_rate are None in the no-signal case (nothing catalog-detectable was present),
    so an empty batch can never masquerade as perfect coverage.
    """

    identifiers_redacted: int
    residual_identifiers: int
    coverage: (
        float | None
    )  # redacted / total detectable; None when nothing was detectable
    residual_rate: (
        float | None
    )  # residual / total detectable; None when nothing was detectable
    drift: (
        float | None
    )  # coverage - baseline_coverage; None without baseline or coverage


@dataclass
class RedactionResult:
    output: Any  # same shape as the input (str or dict), a fresh deep copy
    sli: RedactionSLI


# ── catalog validation ────────────────────────────────────────────────────────


def validate_catalog(catalog: list[FieldClass]) -> None:
    """Reject patterns that are over-long or have an obvious catastrophic-backtracking shape.

    A guard, not a complete defence — see the module docstring on the catalog-trust posture.
    """
    for fc in catalog:
        if fc.kind == "regex" and fc.pattern:
            if len(fc.pattern) > MAX_PATTERN_LENGTH:
                raise ValueError(
                    f"catalog pattern for {fc.name!r} exceeds {MAX_PATTERN_LENGTH} chars"
                )
            if _NESTED_QUANTIFIER.search(fc.pattern):
                raise ValueError(
                    f"catalog pattern for {fc.name!r} has a nested unbounded quantifier "
                    "(catastrophic-backtracking risk); rewrite it or use a linear-time engine"
                )
            re.compile(
                fc.pattern
            )  # surface invalid regex as a clear ValueError-equivalent


# ── span helpers (distinct-identifier counting, no double-count) ───────────────


def _compiled(
    catalog: list[FieldClass], *, enabled_only: bool
) -> list[re.Pattern[str]]:
    return [
        re.compile(fc.pattern)
        for fc in catalog
        if fc.kind == "regex" and fc.pattern and (fc.enabled or not enabled_only)
    ]


def _spans(text: str, patterns: list[re.Pattern[str]]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pat in patterns:
        for m in pat.finditer(text):
            if m.end() > m.start():
                spans.append((m.start(), m.end()))
    return spans


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping/adjacent spans so one identifier matched by several patterns counts once."""
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _overlaps(span: tuple[int, int], others: list[tuple[int, int]]) -> bool:
    # Strict half-open overlap: touching spans (end == start) do NOT overlap. (Note `_merge`
    # uses `<=`, i.e. it joins adjacent spans; the asymmetry is intentional and only matters
    # if these helpers are reused — here an enabled span is always interior to its full span.)
    return any(span[0] < o[1] and o[0] < span[1] for o in others)


def _redact_text_spans(text: str, catalog: list[FieldClass]) -> tuple[str, int, int]:
    """Return (output, redacted_count, residual_count) for free text.

    Counting is on the ORIGINAL text via merged spans (so placeholders are never re-scanned):
      total detectable = merged spans from the FULL catalog (incl. disabled classes)
      redacted         = total spans that an ENABLED class also covers
      residual         = total spans not covered by any enabled class (e.g. a disabled class)
    """
    enabled_spans = _merge(_spans(text, _compiled(catalog, enabled_only=True)))
    full_spans = _merge(_spans(text, _compiled(catalog, enabled_only=False)))
    # Residual attribution favors the enabled class: if an enabled identifier sits *inside* a
    # larger disabled-class match (e.g. email enabled within a disabled URL), the merged span
    # counts as redacted even though the disabled tail survives. Non-overlapping disabled matches
    # are counted residual correctly. This favours under-reporting residual only in that nested case.
    redacted = sum(1 for s in full_spans if _overlaps(s, enabled_spans))
    residual = len(full_spans) - redacted

    # Rebuild output, replacing each enabled span with the placeholder (right-to-left).
    out = text
    for start, end in sorted(enabled_spans, reverse=True):
        out = out[:start] + _PLACEHOLDER + out[end:]
    return out, redacted, residual


def _build_sli(
    redacted: int, residual: int, baseline_coverage: float | None
) -> RedactionSLI:
    total = redacted + residual
    if (
        total == 0
    ):  # no-signal: nothing catalog-detectable was present — do not fabricate 1.0
        return RedactionSLI(0, 0, coverage=None, residual_rate=None, drift=None)
    coverage = redacted / total
    residual_rate = residual / total
    drift = None if baseline_coverage is None else coverage - baseline_coverage
    return RedactionSLI(redacted, residual, coverage, residual_rate, drift)


# ── public API ─────────────────────────────────────────────────────────────────


def redact_text(
    text: str, catalog: list[FieldClass], *, baseline_coverage: float | None = None
) -> RedactionResult:
    """Redact free text using the enabled regex classes in `catalog`."""
    validate_catalog(catalog)
    out, redacted, residual = _redact_text_spans(text, catalog)
    return RedactionResult(
        output=out, sli=_build_sli(redacted, residual, baseline_coverage)
    )


def _redact_value(value: Any, catalog: list[FieldClass]) -> tuple[Any, int, int]:
    """Recurse into a value, redacting strings and nested containers. Returns (copy, redacted, residual)."""
    if isinstance(value, str):
        return _redact_text_spans(value, catalog)
    if isinstance(value, dict):
        return _redact_mapping(value, catalog)
    if isinstance(value, list):
        new_list: list[Any] = []
        redacted = residual = 0
        for item in value:
            nv, r, res = _redact_value(item, catalog)
            new_list.append(nv)
            redacted += r
            residual += res
        return new_list, redacted, residual
    # Non-string scalar (int/float/bool/None): deep-copied, never aliased; not scanned.
    return copy.deepcopy(value), 0, 0


def _redact_mapping(record: dict, catalog: list[FieldClass]) -> tuple[dict, int, int]:
    enabled_fields = {
        fc.field_name
        for fc in catalog
        if fc.kind == "field" and fc.field_name and fc.enabled
    }
    all_fields = {
        fc.field_name for fc in catalog if fc.kind == "field" and fc.field_name
    }
    out: dict = {}
    redacted = residual = 0
    for key, value in record.items():
        if key in enabled_fields:
            out[key] = _PLACEHOLDER
            redacted += 1
        elif key in all_fields:
            # A declared PHI field whose class is disabled: left in place → a measured residual.
            out[key] = copy.deepcopy(value)
            residual += 1
        else:
            nv, r, res = _redact_value(value, catalog)
            out[key] = nv
            redacted += r
            residual += res
    return out, redacted, residual


def redact_record(
    record: dict, catalog: list[FieldClass], *, baseline_coverage: float | None = None
) -> RedactionResult:
    """Redact a structured record without mutating or aliasing the caller's original.

    `field`-kind classes redact a named field wholesale (disabled ones count as residual);
    `regex`-kind classes scan every string value, recursing into nested dicts/lists. The returned
    structure is a fresh deep copy — nothing is retained here.
    """
    validate_catalog(catalog)
    out, redacted, residual = _redact_mapping(record, catalog)
    return RedactionResult(
        output=out, sli=_build_sli(redacted, residual, baseline_coverage)
    )


def expert_determination(*_args: Any, **_kwargs: Any) -> NoReturn:
    """Named extension point for the HIPAA Expert Determination de-identification method.

    Not implemented in this pack — Safe Harbor (rule-based) is the only supported method
    here. Raising keeps data from silently passing through an unimplemented path.
    """
    raise NotImplementedError(
        "Expert Determination is not implemented; this component performs Safe Harbor "
        "rule-based redaction only. Wire a determination provider before using this hook."
    )
