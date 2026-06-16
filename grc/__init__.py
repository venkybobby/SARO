"""SARO AI-GRC audit platform.

A cohesive subsystem (GRC epics 1–6) that governs the AI-system portfolio:
registry + risk tiering, an append-only evidence/provenance layer, the
output-audit orchestrator with automated checks and risk-scoring, framework
citation verification, and the lifecycle gate + named-human sign-off.

Everything reads its policy values from :mod:`grc.policy` (STORY-331) and emits
results conforming to the JSON contract in :mod:`grc.contract` (STORY-328).
"""
