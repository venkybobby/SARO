"""RP-PROMPT-INJECTION — deterministic, evidence-only prompt-injection detector.

Core scoring never calls an external model (CLAUDE.md Non-Negotiable #1); this
package is pure-Python normalization + heuristic matching only.
"""
