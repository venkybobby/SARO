# Product Analytics — Founder Query Set

**Story:** STORY-381 · Companion: [event-schema.md](event-schema.md)

The fastest path is `saro analytics-summary` (event counts + the two key
funnels). The SQL below is for ad-hoc questions the summary does not answer.
Every query is over `product_events`, which carries no PII by construction — so
these run with operator authority and produce no personal data.

## Event volume over time

```sql
SELECT event_name, date_trunc('day', created_at) AS day, count(*)
FROM product_events
GROUP BY event_name, day
ORDER BY day DESC, event_name;
```

## Funnel: login → attestation view (adoption of the core artifact)

```sql
SELECT
  count(*) FILTER (WHERE event_name = 'login')               AS logins,
  count(*) FILTER (WHERE event_name = 'attestation_viewed')  AS attestation_views
FROM product_events
WHERE created_at >= now() - interval '30 days';
```

## Funnel: subscribe → first evaluation (activation)

```sql
SELECT
  count(DISTINCT tenant_id) FILTER (WHERE event_name = 'rule_pack_subscribed') AS subscribed_tenants,
  count(DISTINCT tenant_id) FILTER (WHERE event_name = 'first_evaluation')     AS activated_tenants
FROM product_events;
```

`first_evaluation` fires once per tenant, so `count(DISTINCT tenant_id)` and
`count(*)` are equal for it — the activation count is unambiguous.

## Compliance Hub artifact adoption (by type)

```sql
SELECT properties->>'artifact_type' AS artifact, count(*)
FROM product_events
WHERE event_name = 'compliance_hub_artifact_viewed'
GROUP BY artifact
ORDER BY count(*) DESC;
```

## Persona mix at login

```sql
SELECT properties->>'persona' AS persona, count(*)
FROM product_events
WHERE event_name = 'login'
GROUP BY persona
ORDER BY count(*) DESC;
```

## What you cannot query — and why

There is no query that returns an individual user's activity: the events carry a
tenant id, never a user id or email. That is deliberate (event-schema.md). If you
need actor-level attribution for a security question, that lives in the audit
trail (STORY-366 / FND-065), behind authorization — a different system with a
different access model, not the analytics table.
