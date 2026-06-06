-- SAR-010: Unified Control Library
-- Two tables: controls (one row per control) and control_framework_mappings (many-to-many)

CREATE TABLE IF NOT EXISTS controls (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    control_id          VARCHAR(50)  UNIQUE NOT NULL,
    title               VARCHAR(500) NOT NULL,
    description         TEXT,
    control_type        VARCHAR(50)  NOT NULL DEFAULT 'detective',
    status              VARCHAR(20)  NOT NULL DEFAULT 'active',
    evidence_count      INTEGER      NOT NULL DEFAULT 0,
    last_assessed_date  TIMESTAMPTZ,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS control_framework_mappings (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    control_id       UUID        NOT NULL REFERENCES controls(id) ON DELETE CASCADE,
    framework        VARCHAR(50) NOT NULL,
    clause_reference VARCHAR(100),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for fast framework-filtered queries (SAR-010 FR-03)
CREATE INDEX IF NOT EXISTS idx_cfm_control_id ON control_framework_mappings(control_id);
CREATE INDEX IF NOT EXISTS idx_cfm_framework  ON control_framework_mappings(framework);
