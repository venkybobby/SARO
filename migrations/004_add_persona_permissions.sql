-- Add persona_role to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS persona_role VARCHAR(50);

-- Create persona_permissions table
CREATE TABLE IF NOT EXISTS persona_permissions (
    id SERIAL PRIMARY KEY,
    persona_role VARCHAR(50) NOT NULL UNIQUE,
    allowed_tabs TEXT NOT NULL DEFAULT '[]',
    allowed_actions TEXT NOT NULL DEFAULT '[]',
    denied_actions TEXT NOT NULL DEFAULT '[]',
    trace_mode VARCHAR(20) NOT NULL DEFAULT 'executive',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed default permissions
INSERT INTO persona_permissions (persona_role, allowed_tabs, allowed_actions, denied_actions, trace_mode)
VALUES
('compliance_lead',
 '["dashboard","compliance_hub","trace_view","evidence_export","claims_matrix","how_saro_reasons","dpa_governance","ir_plan","onboarding","upload"]',
 '["evidence_export","verify_chain","onboarding","trace_executive","claims_matrix","dpa"]',
 '["rule_pack_admin","gdpr_erasure","admin_settings","rule_packs","coverage_gap","remediation"]',
 'executive'),
('risk_officer',
 '["dashboard","risk_summary","vendor_risk","ir_plan","trace_view"]',
 '["risk_summary","vendor_risk","board_pdf_export","ir_plan","trace_executive"]',
 '["rule_pack_admin","gdpr_erasure","admin_settings","remediation","claims_matrix"]',
 'executive'),
('ai_auditor',
 '["dashboard","trace_view","evidence_export","rule_packs","coverage_gap","remediation","drift_alerts","upload"]',
 '["trace_technical","rule_packs","coverage_gap","remediation","drift_alerts","audit_crud"]',
 '["gdpr_erasure","risk_summary_board","claims_matrix","admin_settings"]',
 'technical'),
('admin',
 '["dashboard","compliance_hub","trace_view","evidence_export","risk_summary","vendor_risk","claims_matrix","how_saro_reasons","dpa_governance","ir_plan","rule_packs","coverage_gap","remediation","drift_alerts","onboarding","upload","admin_settings"]',
 '["*"]',
 '[]',
 'technical')
ON CONFLICT (persona_role) DO NOTHING;
