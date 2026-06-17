"""STORY-337 — Claims-consistency guard (locked Compliance Claims Matrix).

Makes the Compliance Claims Matrix machine-checkable: the locked claims live here
as structured, versioned assertions, and a few mechanical checks fail CI when a
story / PR / doc contradicts one. "Prompts suggest, hooks enforce, CI guarantees"
applied to claims integrity. This is deliberately pragmatic — a registry + an
integrity lock + targeted checks, not a general NLP contradiction detector
(explicitly out of scope). The mechanical checks grow over time.

What is enforced
----------------
* **Integrity** — a locked claim cannot change silently. The committed digest
  (``claims_registry.lock.json``) must match the claims; any edit fails CI until
  the lock is deliberately regenerated (``python -m grc.guards.claims_registry
  --update``) and the change is recorded in ``docs/CLAIMS_AUDIT_LOG.md``.
* **External-model claim** — delegated to STORY-336: the product path must make
  no third-party hosted-model call at runtime (sole disclosed exception: the
  off-by-default Gate-3 judge, allowlisted there).
* **Framing** — AIGP must not be described as a "framework" or as a
  "certification" SARO issues (matrix: AIGP = principles evaluation only). The
  broad forbidden-phrase repo scan remains owned by
  ``scripts/evf_retrospective_audit.py``; this check is the durable, in-package
  complement focused on the locked AIGP framing.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from grc.guards.external_model import (
    ExternalModelInvariantViolation,
    assert_clean_product_path,
)

REGISTRY_VERSION = "1.0.0"

_LOCK_PATH = Path(__file__).with_name("claims_registry.lock.json")
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Repo-relative paths/prefixes that legitimately enumerate forbidden phrasing (the
# matrix's own "Forbidden" columns, the audit log) or document non-SARO human
# credentials (the EVF SME-process tree). Anchored to exact paths/prefixes so a
# new file cannot inherit the exemption merely by reusing a basename.
_FRAMING_EXCLUDE_PATHS = frozenset(
    {
        "docs/COMPLIANCE_CLAIMS_MATRIX.md",
        "docs/compliance-claims.md",
        "docs/CLAIMS_AUDIT_LOG.md",
    }
)
_FRAMING_EXCLUDE_PREFIXES = (
    "docs/evf/",  # internal SME-validation process docs (human IAPP-AIGP creds)
)

# Inline opt-out for a line that deliberately quotes forbidden phrasing.
_SUPPRESS_MARK = "claims-allow"


class ClaimsRegistryError(RuntimeError):
    """Raised when the locked-claims registry is tampered with or contradicted."""


@dataclass(frozen=True)
class LockedClaim:
    """One locked claim from the Compliance Claims Matrix, as an assertion."""

    id: str
    statement: str
    source: str  # matrix section / non-negotiable reference
    mechanical: str  # "external_model" | "framing" | "manual"


# The seven locked claims seeded from the Compliance Claims Matrix. Worded to
# match the matrix exactly (incl. the SARO-102 disclosed Gate-3 exception) so the
# registry never contradicts the matrix it is derived from.
LOCKED_CLAIMS: tuple[LockedClaim, ...] = (
    LockedClaim(
        id="no-external-model-runtime",
        statement=(
            "SARO's product path makes no call to a third-party hosted model API "
            "at runtime. The sole disclosed exception is the optional, "
            "off-by-default Gate-3 LLM judge, which runs only when a tenant sets "
            "its API key. Mechanically enforced by STORY-336."
        ),
        source="COMPLIANCE_CLAIMS_MATRIX §SARO-102 / Non-Negotiable #1",
        mechanical="external_model",
    ),
    LockedClaim(
        id="no-compliance-certification",
        statement=(
            "SARO never certifies, signs, or endorses compliance. It provides "
            "evidence packages; certification requires human authority."
        ),
        source="COMPLIANCE_CLAIMS_MATRIX — Certification row",
        mechanical="manual",
    ),
    LockedClaim(
        id="human-in-the-loop",
        statement=(
            "SARO always requires human-in-the-loop review and sign-off; it never "
            "auto-certifies."
        ),
        source="Non-Negotiable #5 / AIGP row",
        mechanical="manual",
    ),
    LockedClaim(
        id="no-write-to-client",
        statement=(
            "SARO never writes to client systems; its integration posture is "
            "read-only across all connectors."
        ),
        source="Non-Negotiable #3 / #6",
        mechanical="manual",
    ),
    LockedClaim(
        id="aigp-principles-only",
        statement=(
            "AIGP support is principles evaluation only — never described as a "
            "'framework' or as a 'certification' SARO issues."
        ),
        source="COMPLIANCE_CLAIMS_MATRIX — AIGP Principles",
        mechanical="framing",
    ),
    LockedClaim(
        id="eu-ai-act-evidence-only",
        statement=(
            "EU AI Act coverage is evidence support for Articles 9/13/17 only; "
            "SARO makes no legal classification or conformity determination."
        ),
        source="COMPLIANCE_CLAIMS_MATRIX — EU AI Act",
        mechanical="manual",
    ),
    LockedClaim(
        id="iso-42001-lifecycle-only",
        statement=(
            "ISO 42001 support is document-lifecycle linking and control-objective "
            "support only; SARO issues no certificates."
        ),
        source="COMPLIANCE_CLAIMS_MATRIX — ISO 42001",
        mechanical="manual",
    ),
)


# --- integrity lock ---------------------------------------------------------


def registry_digest() -> str:
    """A stable SHA-256 over the version + every locked claim (order-independent)."""
    payload = {
        "version": REGISTRY_VERSION,
        "claims": sorted(
            [dataclasses.asdict(c) for c in LOCKED_CLAIMS], key=lambda c: c["id"]
        ),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _locked_digest() -> str | None:
    if not _LOCK_PATH.exists():
        return None
    try:
        return json.loads(_LOCK_PATH.read_text(encoding="utf-8")).get("digest")
    except (json.JSONDecodeError, OSError):
        return None


def write_lock() -> None:
    """Record the current version + digest. Regenerating this is the explicit,
    reviewable act of changing a locked claim."""
    _LOCK_PATH.write_text(
        json.dumps({"version": REGISTRY_VERSION, "digest": registry_digest()}, indent=2)
        + "\n",
        encoding="utf-8",
    )


def assert_registry_integrity() -> None:
    """Raise if the committed lock does not match the current claims."""
    expected = _locked_digest()
    current = registry_digest()
    if expected is None:
        raise ClaimsRegistryError(
            f"claims registry lock missing at {_LOCK_PATH.name}; generate it with "
            "`python -m grc.guards.claims_registry --update`."
        )
    if expected != current:
        raise ClaimsRegistryError(
            "Locked-claims registry changed without an explicit, logged decision. "
            f"digest {current} != committed {expected}. A locked claim must not "
            "change silently: record the decision in docs/CLAIMS_AUDIT_LOG.md, bump "
            "REGISTRY_VERSION, then regenerate the lock with "
            "`python -m grc.guards.claims_registry --update`."
        )


# --- framing checks ---------------------------------------------------------


@dataclass(frozen=True)
class FramingViolation:
    path: str
    lineno: int
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.path}:{self.lineno} [{self.rule}] {self.detail}"


# Each rule: (id, compiled pattern, human detail). The certification rule flags
# broadly; the matrix-approved form ("AIGP-certified human reviewer/auditor") is
# excluded separately by span so a trailing reviewer-noun cannot silence a real
# violation (e.g. "AIGP certification reviewer badges").
_FRAMING_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "aigp-as-framework",
        re.compile(r"AIGP[\s\-]+frameworks?\b", re.IGNORECASE),
        "AIGP is a principles evaluation, not a 'framework' (matrix: AIGP "
        "Principles only).",
    ),
    (
        "aigp-as-certification",
        re.compile(r"AIGP[\s\-]+certif(?:y|ies|ied|ication|icate)s?\b", re.IGNORECASE),
        "SARO never issues AIGP certification (approved: 'AIGP-certified human "
        "reviewer').",
    ),
    (
        "certification-under-aigp",
        re.compile(r"certif(?:y|ied|ication)\s+under\s+AIGP", re.IGNORECASE),
        "SARO never certifies under AIGP.",
    ),
)

# The single matrix-approved usage: a *human* who is AIGP-certified. A cert match
# inside one of these spans is the approved phrase, not a SARO certification claim.
_AIGP_APPROVED = re.compile(
    r"AIGP[\s\-]+certified\s+(?:human\s+reviewer|reviewer|auditor|personnel|human)\b",
    re.IGNORECASE,
)

_DASHES = "‐‑‒–—―−"


def _normalize(line: str) -> str:
    """Fold unicode dashes/nbsp and strip markdown emphasis so trivial visual
    variants (``AIGP‑certification``, ``**AIGP** certification``) cannot evade."""
    text = unicodedata.normalize("NFKC", line)
    for dash in _DASHES:
        text = text.replace(dash, "-")
    text = text.replace(" ", " ")
    return re.sub(r"[*_`]+", "", text)


def _within(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    return any(s <= span[0] and span[1] <= e for s, e in spans)


def check_framing(text: str) -> list[FramingViolation]:
    """Return framing violations in ``text`` (per-line, with inline suppression)."""
    violations: list[FramingViolation] = []
    for lineno, line in enumerate(text.splitlines() or [text], start=1):
        if _SUPPRESS_MARK in line:
            continue
        norm = _normalize(line)
        approved = [m.span() for m in _AIGP_APPROVED.finditer(norm)]
        for rule_id, pattern, detail in _FRAMING_RULES:
            for m in pattern.finditer(norm):
                if rule_id == "aigp-as-certification" and _within(m.span(), approved):
                    continue
                violations.append(FramingViolation("(inline)", lineno, rule_id, detail))
                break
    return violations


def scan_files(
    paths: Iterable[Path | str], *, repo_root: Path | str
) -> list[FramingViolation]:
    """Scan text files for framing violations, excluding the claims-source docs."""
    repo = Path(repo_root)
    out: list[FramingViolation] = []
    for p in paths:
        path = Path(p)
        try:
            rel = path.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            rel = path.as_posix()
        if rel in _FRAMING_EXCLUDE_PATHS or rel.startswith(_FRAMING_EXCLUDE_PREFIXES):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for v in check_framing(text):
            out.append(dataclasses.replace(v, path=rel))
    return out


# --- external-model claim (delegated to STORY-336) --------------------------


def verify_external_model_claim(
    *,
    repo_root: Path | str | None = None,
    roots: Iterable[Path | str] | None = None,
) -> str | None:
    """Return a violation message if the external-model claim is contradicted."""
    try:
        assert_clean_product_path(repo_root=repo_root, roots=roots)
    except ExternalModelInvariantViolation as exc:
        return str(exc)
    return None


# --- CI entry point ---------------------------------------------------------


def _docs_and_stories(repo: Path) -> list[Path]:
    """External-facing markdown surfaces: stories, docs, and root *.md.

    ``scan_files`` applies the path-anchored exclusions (the claims-source docs
    and the EVF SME tree). Frontend UI copy is covered by the frontend gate, not
    here (a documented limitation — see the story's traceability section)."""
    targets = sorted((repo / "specs" / "stories").glob("*.md"))
    targets += sorted(repo.glob("*.md"))  # root README / CLAUDE.md / etc.
    docs = repo / "docs"
    if docs.is_dir():
        targets += sorted(docs.rglob("*.md"))
    return targets


def main(argv: list[str] | None = None) -> int:
    """CI entry: ``python -m grc.guards.claims_registry`` (``--update`` rewrites lock)."""
    argv = sys.argv[1:] if argv is None else argv
    if "--update" in argv:
        write_lock()
        print(f"Wrote {_LOCK_PATH.name} (version {REGISTRY_VERSION}).")
        return 0

    failures: list[str] = []
    try:
        assert_registry_integrity()
    except ClaimsRegistryError as exc:
        failures.append(str(exc))

    ext = verify_external_model_claim()
    if ext:
        failures.append(ext)

    framing = scan_files(_docs_and_stories(_REPO_ROOT), repo_root=_REPO_ROOT)
    failures.extend(str(v) for v in framing)

    if failures:
        print("Claims-consistency guard FAILED (STORY-337):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(
        f"STORY-337 OK — {len(LOCKED_CLAIMS)} locked claims intact; no external-model "
        "or AIGP-framing contradictions."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
