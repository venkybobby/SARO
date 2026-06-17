"""SARO QA lab — OFFLINE validation tooling. NOT product/runtime code.

This package is the **only** sanctioned external-model use in the SARO repo
(STORY-338), and it is deliberately isolated from the product path: STORY-336's
guard (`grc.guards.external_model`, `LAB_PACKAGE = "qa_lab"`) fails CI if any
product/runtime module imports `qa_lab`. Nothing here may be wired into
`main.py`, `routers/`, `services/`, `engine.py`, or `grc/`.

It exists to *build ground truth* for the validation corpus — an LLM-as-judge
pre-labels/verifies samples offline, and a human adjudicates before any label is
accepted. The judge never has the final say.
"""
