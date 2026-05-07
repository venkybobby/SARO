---
name: rule-pack-edit
description: Triggered when editing files in rule_packs/. Enforces schema validation, versioning discipline, and vertical constraints for SARO rule packs.
---

# Rule Pack Edit Skill

## Trigger Conditions
Activate when any file under `rule_packs/` is created, modified, or deleted.

## Schema Requirements

Every rule pack JSON/YAML must include these top-level fields:

```json
{
  "id": "rp_<vertical>_<slug>_v<semver>",
  "version": "8.0.0",
  "vertical": "finance|healthcare|technology|government",
  "name": "Human-readable name",
  "description": "What this pack detects",
  "rules": [...],
  "created_at": "ISO-8601",
  "updated_by": "github-username"
}
```

Each rule entry:
```json
{
  "rule_id": "R-<vertical>-<4-digit-seq>",
  "category": "bias|toxicity|hallucination|pii|drift|custom",
  "weight": 0.0,
  "threshold": 0.0,
  "description": "...",
  "remediation": "..."
}
```

## Validation Rules

- `weight` values across all rules in a pack must sum to ≤ 1.0.
- `threshold` must be in range [0.0, 1.0].
- `version` must match SARO global version (`8.0.0`) — bump pack version independently using `pack_version` field for pack-specific changes.
- `vertical` must be one of the four supported values; mixed-vertical packs are forbidden.
- `rule_id` sequence numbers must not collide within a vertical.

## Versioning Protocol

1. Increment `pack_version` (semver) for any rule weight/threshold change.
2. Add changelog entry to `rule_packs/CHANGELOG.md` with date, author, and diff summary.
3. Never delete a rule — set `deprecated: true` and `deprecated_at` instead.
4. Tag the git commit: `chore(rules): bump <pack-id> to <new-version>`.

## Vertical Constraints

| Vertical | Extra Validation |
|---|---|
| Finance | Must include at least one `hallucination` and one `pii` rule |
| Healthcare | PHI rules mandatory; `pii` weight ≥ 0.25 |
| Government | NIST AI RMF mapping field required per rule |
| Technology | No vertical-specific mandatory rules |

## Hook Behaviour
The `PreToolUse/Write(rule_packs/*)` hook will block this write and prompt for confirmation. You must receive explicit user approval before proceeding with any rule pack change.
