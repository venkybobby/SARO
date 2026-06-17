"""STORY-336 — No-external-model-at-runtime invariant guard.

SARO's locked claim — the GRC output-audit / product path never calls a
third-party hosted model API at runtime — is enforced here in code, not trusted
to reviewers. A static guard walks the product/runtime path and fails (CI exit
1) the moment a module imports a forbidden external-model SDK or references a
hosted model endpoint. This is the durable fix for the class of error DEC-4
represented.

Definition in force (STORY-335/336)
-----------------------------------
An "external AI model" is a *third-party hosted model API* that transmits client
data outside SARO. A **self-hosted** model running inside SARO infra (e.g.
ollama / a localhost inference server) does **not** violate the claim — its
SDKs and endpoints are deliberately absent from the denylists below.

What this guard does and does NOT catch
----------------------------------------
The control is static import/call-site analysis. It catches: direct ``import`` /
``from ... import`` of a denylisted SDK; ``importlib.import_module("...")`` and
``__import__("...")`` with a *literal* module name; and hosted-model endpoints
that appear as *literal* string constants. It does **not** catch a module name
or URL assembled at runtime (f-strings, concatenation, ``getattr``, base64), nor
transitive reaches through a non-scanned package. Closing that class is the job
of the network-egress policy fast-follow (out of scope here, per the spec); the
import denylist is the real control, the endpoint scan is defence-in-depth.

Two explicit, documented exemptions
------------------------------------
* ``engine.py`` — the legacy scoring engine's optional, off-by-default Gate-3
  LLM judge. A disclosed exception under COMPLIANCE_CLAIMS_MATRIX §SARO-102
  (owner decision 2026-06-12). It is **allowlisted, not invisible**: the guard
  still detects the import, and a dedicated test proves the allowlist — not the
  absence of a call — is what lets it pass.
* the offline QA-lab package (:data:`LAB_PACKAGE`, built in STORY-338) — the
  only sanctioned external-model use. It lives outside the product path; the
  guard additionally fails if any product-path module *imports* it, proving the
  lab is unreachable from the runtime path.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# Top-level package names (or exact dotted paths) of third-party *hosted* model
# SDKs and the idiomatic router/framework on-ramps to them. Self-hosted runtimes
# (ollama, vllm, llama_cpp, transformers, sentence_transformers, ...) are
# intentionally excluded — they run inside SARO infra.
FORBIDDEN_PROVIDER_MODULES: frozenset[str] = frozenset(
    {
        # Direct provider SDKs.
        "anthropic",
        "openai",
        "cohere",
        "mistralai",
        "google.generativeai",  # legacy google SDK
        "google.genai",  # current google-genai SDK that superseded it
        "vertexai",
        "google.cloud.aiplatform",
        "replicate",
        "together",
        "groq",
        "ai21",
        "anyscale",
        "huggingface_hub",  # hosted Inference API
        "fireworks",
        "openrouter",
        "deepseek",
        # Multi-provider routers / framework on-ramps (the modern default way an
        # engineer reaches a hosted model).
        "litellm",
        "langchain_openai",
        "langchain_anthropic",
        "langchain_google_genai",
        "langchain_cohere",
        "langchain_mistralai",
    }
)

# Substrings of hosted model API endpoints (incl. boto3 Bedrock service ids).
# Matched against literal string constants.
FORBIDDEN_ENDPOINT_SUBSTRINGS: frozenset[str] = frozenset(
    {
        "api.anthropic.com",
        "api.openai.com",
        "openai.azure.com",
        "api.cohere.ai",
        "api.cohere.com",
        "generativelanguage.googleapis.com",
        "aiplatform.googleapis.com",
        "api.mistral.ai",
        "api.together.xyz",
        "api.groq.com",
        "api.replicate.com",
        "openrouter.ai",
        "api.fireworks.ai",
        "api.deepseek.com",
        "bedrock-runtime",  # boto3.client("bedrock-runtime", ...)
        "bedrock-agent-runtime",
    }
)

# Names of dynamic-import callables whose literal string argument names a module.
_DYNAMIC_IMPORTERS = frozenset(
    {"__import__", "import_module", "importlib.import_module"}
)

# The offline QA-lab package (STORY-338). Sanctioned external-model use, but
# unreachable from product code: a product-path import of it is a violation.
LAB_PACKAGE: str = "qa_lab"

# Paths (POSIX, relative to repo root) exempt from the scan. Each entry is a
# documented exception, never a silent skip.
DEFAULT_ALLOWLIST: frozenset[str] = frozenset(
    {
        # Disclosed, off-by-default Gate-3 LLM judge — COMPLIANCE_CLAIMS_MATRIX §SARO-102.
        "engine.py",
    }
)

# Product package directories scanned in full. ``middleware`` is a namespace
# package (no __init__) but is unambiguously runtime (main.py imports it).
PRODUCT_PACKAGE_DIRS: tuple[str, ...] = ("grc", "routers", "services", "middleware")

# Repo-relative path prefixes never scanned: the guard itself (it defines the
# denylists as data) and pyc/git noise.
_SKIP_RELPATH_PREFIXES: tuple[str, ...] = ("grc/guards/",)
_SKIP_DIR_NAMES = frozenset({"__pycache__", ".git"})


@dataclass(frozen=True)
class Violation:
    """One product-path reference to an external model (or to the QA lab)."""

    path: str
    lineno: int
    kind: str  # "import" | "endpoint" | "lab_import"
    name: str
    detail: str

    def __str__(self) -> str:
        return f"{self.path}:{self.lineno} [{self.kind}] {self.name} — {self.detail}"


class ExternalModelInvariantViolation(RuntimeError):
    """Raised when the product path reaches a third-party hosted model API."""


def _top_module(dotted: str) -> str:
    return dotted.split(".", 1)[0]


def _is_forbidden_module(module: str) -> bool:
    if module in FORBIDDEN_PROVIDER_MODULES:
        return True
    # A single-segment denylist entry (e.g. "openai") also blocks its submodules
    # ("openai.types"). Dotted entries (e.g. "google.generativeai") must match
    # exactly so we never block an unrelated top level like "google.cloud.storage".
    single = {m for m in FORBIDDEN_PROVIDER_MODULES if "." not in m}
    return _top_module(module) in single


def _is_lab_module(module: str) -> bool:
    return module == LAB_PACKAGE or module.startswith(LAB_PACKAGE + ".")


def _call_name(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return (
            f"{_call_name(func.value)}.{func.attr}"
            if isinstance(func.value, (ast.Name, ast.Attribute))
            else func.attr
        )
    return ""


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _iter_py_files(root: Path, repo_root: Path) -> Iterable[Path]:
    if root.is_file():
        if root.suffix == ".py":
            yield root
        return
    for path in sorted(root.rglob("*.py")):
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        rel = _rel(path, repo_root)
        if any(rel.startswith(prefix) for prefix in _SKIP_RELPATH_PREFIXES):
            continue
        yield path


def _module_violation(rel: str, lineno: int, module: str) -> Violation | None:
    if _is_forbidden_module(module):
        return Violation(
            rel,
            lineno,
            "import",
            _top_module(module),
            f"reaches forbidden hosted-model SDK {module!r}",
        )
    if _is_lab_module(module):
        return Violation(
            rel,
            lineno,
            "lab_import",
            module,
            "product code imports the offline QA-lab package",
        )
    return None


def _scan_file(path: Path, repo_root: Path) -> list[Violation]:
    rel = _rel(path, repo_root)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        # A file that does not parse cannot be making a static external call we
        # can prove; leave it to the normal lint/compile gates.
        return []

    found: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                v = _module_violation(rel, node.lineno, alias.name)
                if v:
                    found.append(v)
        elif isinstance(node, ast.ImportFrom):
            v = _module_violation(rel, node.lineno, node.module or "")
            if v:
                found.append(v)
        elif isinstance(node, ast.Call):
            # importlib.import_module("openai") / __import__("anthropic")
            if _call_name(node.func) in _DYNAMIC_IMPORTERS and node.args:
                arg0 = node.args[0]
                if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                    v = _module_violation(rel, node.lineno, arg0.value)
                    if v:
                        found.append(v)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            for endpoint in FORBIDDEN_ENDPOINT_SUBSTRINGS:
                if endpoint in node.value:
                    found.append(
                        Violation(
                            rel,
                            node.lineno,
                            "endpoint",
                            endpoint,
                            f"references hosted-model endpoint {endpoint!r}",
                        )
                    )
                    break
    return found


def default_product_roots(repo_root: Path) -> list[Path]:
    """Every top-level ``*.py`` plus each product package dir under ``repo_root``.

    Enumerating dynamically (rather than a fixed file list) means new top-level
    runtime modules — ``config.py``, a future ``settings.py`` — are in scope the
    moment they exist, instead of silently escaping the guard.
    """
    roots: list[Path] = sorted(repo_root.glob("*.py"))
    roots += [repo_root / d for d in PRODUCT_PACKAGE_DIRS if (repo_root / d).is_dir()]
    return roots


def scan_paths(
    roots: Iterable[Path | str],
    *,
    repo_root: Path | str,
    allowlist: frozenset[str] = DEFAULT_ALLOWLIST,
) -> list[Violation]:
    """Scan ``roots`` for product-path external-model use.

    Returns every :class:`Violation` found. Files whose repo-relative POSIX path
    is in ``allowlist`` are skipped (the documented exemptions).
    """
    repo = Path(repo_root)
    violations: list[Violation] = []
    for root in roots:
        for py in _iter_py_files(Path(root), repo):
            if _rel(py, repo) in allowlist:
                continue
            violations.extend(_scan_file(py, repo))
    return violations


def assert_clean_product_path(
    *,
    repo_root: Path | str | None = None,
    roots: Iterable[Path | str] | None = None,
    allowlist: frozenset[str] = DEFAULT_ALLOWLIST,
) -> None:
    """Raise :class:`ExternalModelInvariantViolation` if the product path is dirty.

    ``repo_root`` defaults to the repository root inferred from this module.
    ``roots`` defaults to :func:`default_product_roots`.
    """
    repo = (
        Path(repo_root)
        if repo_root is not None
        else Path(__file__).resolve().parents[2]
    )
    scan_roots = list(roots) if roots is not None else default_product_roots(repo)
    violations = scan_paths(scan_roots, repo_root=repo, allowlist=allowlist)
    if violations:
        listing = "\n  ".join(str(v) for v in violations)
        raise ExternalModelInvariantViolation(
            "No-external-model-at-runtime invariant violated (STORY-336). "
            "A product-path module reaches a third-party hosted model API or the "
            f"offline QA lab:\n  {listing}\n"
            "Self-hosted models are permitted; move external-model use to the "
            "offline QA lab (STORY-338) or add a documented allowlist entry."
        )


def _validate_allowlist(repo_root: Path, allowlist: frozenset[str]) -> list[str]:
    """Return allowlist entries that do not resolve to a real file (typo guard)."""
    return sorted(e for e in allowlist if not (repo_root / e).exists())


def main() -> int:
    """CI entry point: ``python -m grc.guards.external_model``."""
    repo = Path(__file__).resolve().parents[2]
    stale = _validate_allowlist(repo, DEFAULT_ALLOWLIST)
    if stale:
        print(
            f"STORY-336 allowlist references missing path(s): {stale} — "
            "remove or correct the entry.",
            file=sys.stderr,
        )
        return 1
    try:
        assert_clean_product_path(repo_root=repo)
    except ExternalModelInvariantViolation as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("STORY-336 OK — product path is free of external-model calls.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
