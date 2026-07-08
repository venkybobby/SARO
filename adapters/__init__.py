"""SARO ingestion adapters — read-only mappers from a customer's existing AI
telemetry into SARO's evidence streams (async audits + observation coverage).

An adapter NEVER calls a hosted model. It parses logs the customer already
produced. This package is scanned by the STORY-336 external-model guard
(``grc.guards.external_model.PRODUCT_PACKAGE_DIRS``) precisely so that invariant
is enforced here, not trusted to reviewers.
"""
