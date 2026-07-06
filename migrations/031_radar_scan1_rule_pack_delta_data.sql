-- Migration 031: Rule-pack delta data — radar scan #1 (STORY-CHUB-011 companion)
--
-- Exports the Supabase-applied data migration `radar_scan1_rule_pack_delta_data`
-- (version 20260704194907, applied out-of-band via MCP on 2026-07-04) into the repo
-- migration set so CI-managed schema_migrations and the live DB do not diverge
-- (integrated-delivery rule). Companion to migration 029 (the columns migration).
--
-- These are the 28 DRAFT_UNVALIDATED / 7 RETIRED status transitions + 4 new draft
-- governance rows that STORY-CHUB-011's server-side filter must hide from customer
-- surfaces. Guarded so re-running on the live project (already applied) is a no-op
-- and a fresh environment that lacks the target rows simply sets nothing.
--
-- Rollback note (from the live migration): touched eu_ai_act_rules ids 9-24, 34-41;
-- governance_rules framework 'US EO 14110'; inserts under 'US Colorado SB 189' and
-- 'US Texas TRAIGA'.

-- RD1-001/002: Annex III + Art 6 + high-risk chapter Arts 9-17 + deployer Arts 26/27
UPDATE eu_ai_act_rules
SET applicability_date = DATE '2027-12-02',
    validation_status = 'DRAFT_UNVALIDATED',
    last_updated = DATE '2026-07-04'
WHERE id IN (9,10,11,12,13,14,15,16,17,18,19,20,34,35,36,37,38,39,40,41);

-- RD1-003: Article 50 transparency
UPDATE eu_ai_act_rules
SET applicability_date = DATE '2026-08-02',
    validation_status = 'DRAFT_UNVALIDATED',
    last_updated = DATE '2026-07-04'
WHERE id IN (21,22,23,24);

-- RD1-003 grace note on Art 50(1) (idempotent: only append the note once)
UPDATE eu_ai_act_rules
SET description = COALESCE(description,'') || ' [Radar RD1-003, 2026-07-04: Digital Omnibus grace - systems on market before 2026-08-02 must meet machine-readable marking by 2026-12-02. Mapping of grace to Art 50(1) pending SME confirmation.]'
WHERE id = 21
  AND (description IS NULL OR description NOT LIKE '%Radar RD1-003%');

-- RD1-011: soft-retire revoked EO 14110 framework
UPDATE governance_rules
SET validation_status = 'RETIRED',
    last_updated = DATE '2026-07-04'
WHERE framework_name = 'US EO 14110';

-- RD1-007/008: new state frameworks, draft status (idempotent: skip if rule_id exists)
INSERT INTO governance_rules (framework_name, rule_id, category, description, obligations, last_updated, validation_status)
SELECT v.framework_name, v.rule_id, v.category, v.description, v.obligations, v.last_updated, v.validation_status
FROM (VALUES
  ('US Colorado SB 189','CO-SB189-1','ADMT Disclosure','Disclosure obligations for covered automated decision-making technologies under Colorado SB 189 (signed 2026-05-14; replaces Colorado AI Act). Effective 2027-01-01.','Deployer must disclose ADMT use to affected consumers per SB 189 disclosure framework.',DATE '2026-07-04','DRAFT_UNVALIDATED'),
  ('US Colorado SB 189','CO-SB189-2','Superseded CAIA Provisions','SB 189 eliminates former CAIA duty of care, deployer risk management program, impact assessments, and AG reporting obligations.','Track superseded obligations for historical mapping only; no active duties.',DATE '2026-07-04','DRAFT_UNVALIDATED'),
  ('US Texas TRAIGA','TX-TRAIGA-1','Safe Harbor - Framework Alignment','TRAIGA affirmative defense for documented alignment with recognized AI risk frameworks (e.g., NIST AI RMF). Effective 2026-01-01.','Maintain documented NIST AI RMF alignment evidence. SARO packaging = evidence-support capability, not legal claim; SME/counsel review required.',DATE '2026-07-04','DRAFT_UNVALIDATED'),
  ('US Texas TRAIGA','TX-TRAIGA-2','Safe Harbor - Testing and Audit Trails','TRAIGA safe harbor factors include adversarial testing and preserved audit trails.','Preserve attestation and audit-trail records suitable as safe-harbor evidence.',DATE '2026-07-04','DRAFT_UNVALIDATED')
) AS v(framework_name, rule_id, category, description, obligations, last_updated, validation_status)
WHERE NOT EXISTS (
    SELECT 1 FROM governance_rules g WHERE g.rule_id = v.rule_id
);
