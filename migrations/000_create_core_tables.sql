-- Migration 000 (create_core_tables): bootstrap the full ORM schema as a
-- baseline so the SQL migration chain (001+) can apply to a *fresh* database.
--
-- In normal deployments, database.create_all_tables() (Base.metadata.create_all)
-- already creates every table below before apply_pending_migrations() runs, so
-- these CREATE TABLE IF NOT EXISTS statements are no-ops there.
--
-- The "Migrations Apply Cleanly (fresh Postgres)" CI job, however, applies only
-- migrations/*.sql via psql against an empty database — without this file,
-- 001_add_rls_policies.sql fails with "relation \"audits\" does not exist"
-- because no earlier migration creates the core tables it enables RLS on.
--
-- Generated from models.py (Base.metadata.sorted_tables) via SQLAlchemy's
-- CreateTable(table, if_not_exists=True).compile(dialect=postgresql.dialect())
-- — regenerate the same way if the ORM schema changes in a way that affects
-- tables referenced by later migrations.
--
-- Sorts before 000_schema_migrations_tracking.sql and 001_add_rls_policies.sql
-- ("000_c" < "000_s" < "001_"), and is itself idempotent / safe to re-run.
--
-- persona_permissions is intentionally NOT included here: 004_add_persona_permissions.sql
-- creates that table with its own (older) schema and seeds it via INSERT, which would
-- fail against the newer models.py shape. Letting 004 create it first preserves the
-- existing migration's behaviour.
--
-- audit_traces.tenant_id and scan_reports.tenant_id are included here (ahead of
-- 002_add_tenant_id_columns.sql) because 001_add_rls_policies.sql creates RLS
-- policies on those tables that reference tenant_id.

CREATE TABLE IF NOT EXISTS ai_incidents (
	id SERIAL NOT NULL,
	incident_id VARCHAR(100),
	title VARCHAR(500),
	date VARCHAR(50),
	description TEXT,
	category VARCHAR(255),
	harm_type VARCHAR(255),
	affected_sector VARCHAR(255),
	url VARCHAR(500),
	source VARCHAR(255),
	is_fixed BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS aigp_principles (
	id SERIAL NOT NULL,
	domain VARCHAR(255),
	subtopic VARCHAR(500),
	key_principles TEXT,
	description TEXT,
	last_updated TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS controls (
	id UUID NOT NULL,
	control_id VARCHAR(50) NOT NULL,
	title VARCHAR(500) NOT NULL,
	description TEXT,
	control_type VARCHAR(50) NOT NULL,
	status VARCHAR(20) NOT NULL,
	evidence_count INTEGER NOT NULL,
	last_assessed_date TIMESTAMP WITH TIME ZONE,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (control_id)
);

CREATE TABLE IF NOT EXISTS demo_requests (
	id UUID NOT NULL,
	first_name VARCHAR(100) NOT NULL,
	last_name VARCHAR(100) NOT NULL,
	email VARCHAR(320) NOT NULL,
	contact_number VARCHAR(50),
	company_name VARCHAR(255),
	message TEXT,
	status VARCHAR(50) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS eu_ai_act_rules (
	id SERIAL NOT NULL,
	article_number VARCHAR(50),
	title VARCHAR(500),
	risk_level VARCHAR(100),
	obligations_providers TEXT,
	obligations_users TEXT,
	description TEXT,
	annex_reference VARCHAR(100),
	source_url VARCHAR(500),
	last_updated TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS governance_rules (
	id SERIAL NOT NULL,
	framework_name VARCHAR(255),
	rule_id VARCHAR(100),
	category VARCHAR(255),
	description TEXT,
	obligations TEXT,
	last_updated TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS mit_risks (
	id SERIAL NOT NULL,
	ev_id VARCHAR(100),
	paper_id VARCHAR(100),
	category_level VARCHAR(50),
	risk_category VARCHAR(255),
	risk_subcategory VARCHAR(255),
	description TEXT,
	additional_ev TEXT,
	causal_entity VARCHAR(255),
	causal_intent VARCHAR(100),
	causal_timing VARCHAR(100),
	domain VARCHAR(255),
	sub_domain VARCHAR(255),
	created_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS nist_ai_rmf_controls (
	id SERIAL NOT NULL,
	function_name VARCHAR(100),
	subcategory_id VARCHAR(50),
	description TEXT,
	key_actions TEXT,
	version VARCHAR(50),
	last_updated TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS notifications (
	id UUID NOT NULL,
	tenant_id UUID NOT NULL,
	type VARCHAR(50) NOT NULL,
	title VARCHAR(255) NOT NULL,
	body TEXT NOT NULL,
	severity VARCHAR(20) NOT NULL,
	read_at TIMESTAMP WITH TIME ZONE,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	metadata_json TEXT NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS tenants (
	id UUID NOT NULL,
	name VARCHAR(255) NOT NULL,
	slug VARCHAR(100) NOT NULL,
	settings_json JSON,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (slug)
);

CREATE TABLE IF NOT EXISTS ai_systems (
	id UUID NOT NULL,
	tenant_id UUID NOT NULL,
	name VARCHAR(500) NOT NULL,
	description TEXT,
	system_owner VARCHAR(320),
	purpose TEXT,
	deployment_context VARCHAR(255),
	eu_ai_act_risk_tier VARCHAR(20),
	last_audit_date TIMESTAMP WITH TIME ZONE,
	current_risk_score INTEGER,
	is_active BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS aims_documents (
	id UUID NOT NULL,
	tenant_id UUID NOT NULL,
	title VARCHAR(500) NOT NULL,
	version VARCHAR(50) NOT NULL,
	effective_date TIMESTAMP WITH TIME ZONE,
	owner_email VARCHAR(320) NOT NULL,
	linked_audit_ids JSON NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS client_configs (
	id UUID NOT NULL,
	tenant_id UUID NOT NULL,
	industry VARCHAR(255),
	size VARCHAR(100),
	primary_contact_name VARCHAR(255),
	primary_contact_email VARCHAR(320),
	sso_enabled BOOLEAN NOT NULL,
	idp_provider VARCHAR(100),
	idp_metadata JSON,
	scim_enabled BOOLEAN NOT NULL,
	scim_endpoint VARCHAR(500),
	scim_bearer_token_hash VARCHAR(64),
	mfa_required BOOLEAN NOT NULL,
	allow_magic_link_fallback BOOLEAN NOT NULL,
	warning_banner_active BOOLEAN NOT NULL,
	token_expire_minutes INTEGER,
	data_region VARCHAR(10),
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (tenant_id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS control_framework_mappings (
	id UUID NOT NULL,
	control_id UUID NOT NULL,
	framework VARCHAR(50) NOT NULL,
	clause_reference VARCHAR(100),
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(control_id) REFERENCES controls (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS github_integrations (
	id UUID NOT NULL,
	tenant_id UUID NOT NULL,
	allowed_repos JSON NOT NULL,
	access_token_hash VARCHAR(64),
	is_active BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	last_scan_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (tenant_id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tenant_risk_configs (
	id UUID NOT NULL,
	tenant_id UUID NOT NULL,
	domain_weights JSON NOT NULL,
	keyword_suppressions JSON NOT NULL,
	max_weight_ceiling FLOAT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (tenant_id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS users (
	id UUID NOT NULL,
	tenant_id UUID NOT NULL,
	email VARCHAR(320) NOT NULL,
	hashed_password VARCHAR(255),
	role VARCHAR(50) NOT NULL,
	persona_role VARCHAR(50),
	is_active BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE,
	UNIQUE (email)
);

CREATE TABLE IF NOT EXISTS audit_events (
	id UUID NOT NULL,
	tenant_id UUID NOT NULL,
	user_id UUID,
	event_type VARCHAR(100) NOT NULL,
	event_data JSON NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE,
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS audits (
	id UUID NOT NULL,
	tenant_id UUID NOT NULL,
	user_id UUID,
	batch_id VARCHAR(100),
	dataset_name VARCHAR(255),
	sample_count INTEGER NOT NULL,
	status VARCHAR(50) NOT NULL,
	prompt_text TEXT,
	raw_output_text TEXT,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	completed_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE,
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
	id UUID NOT NULL,
	triggered_by VARCHAR(50) NOT NULL,
	triggered_by_user_id UUID,
	datasets_requested TEXT NOT NULL,
	started_at TIMESTAMP WITH TIME ZONE NOT NULL,
	completed_at TIMESTAMP WITH TIME ZONE,
	status VARCHAR(20) NOT NULL,
	datasets_attempted INTEGER NOT NULL,
	datasets_passed INTEGER NOT NULL,
	datasets_skipped INTEGER NOT NULL,
	datasets_failed INTEGER NOT NULL,
	total_samples_uploaded INTEGER NOT NULL,
	overall_passed BOOLEAN,
	elapsed_seconds FLOAT,
	run_summary_json TEXT,
	api_url VARCHAR(500) NOT NULL,
	error_message TEXT,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(triggered_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS evf_publication_events (
	id UUID NOT NULL,
	timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
	artefact_identifier VARCHAR(500) NOT NULL,
	qco_reference_number VARCHAR(100) NOT NULL,
	publisher_user_id UUID,
	distribution_channel VARCHAR(50) NOT NULL,
	prev_hash VARCHAR(64),
	event_hash VARCHAR(64),
	idempotency_key VARCHAR(255),
	PRIMARY KEY (id),
	FOREIGN KEY(publisher_user_id) REFERENCES users (id) ON DELETE SET NULL,
	UNIQUE (idempotency_key)
);

CREATE TABLE IF NOT EXISTS evf_sme_engagements (
	id UUID NOT NULL,
	sme_firm_name VARCHAR(255) NOT NULL,
	sme_key_contact VARCHAR(255),
	sme_credential VARCHAR(255),
	framework VARCHAR(50) NOT NULL,
	state VARCHAR(50) NOT NULL,
	state_entered_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	created_by_user_id UUID,
	notes TEXT,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS audit_metadata (
	id UUID NOT NULL,
	audit_id UUID NOT NULL,
	source_model VARCHAR(100),
	ingestion_method VARCHAR(50) NOT NULL,
	vertical VARCHAR(50),
	prompt_s3_key VARCHAR(500),
	output_s3_key VARCHAR(500),
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (audit_id),
	FOREIGN KEY(audit_id) REFERENCES audits (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_traces (
	id UUID NOT NULL,
	audit_id UUID NOT NULL,
	tenant_id UUID,
	gate_id INTEGER NOT NULL,
	gate_name VARCHAR(100) NOT NULL,
	check_type VARCHAR(50) NOT NULL,
	check_name VARCHAR(500) NOT NULL,
	result VARCHAR(20) NOT NULL,
	reason TEXT,
	detail_json JSON,
	remediation_hint TEXT,
	signal_text VARCHAR(500),
	top_sample_ids JSON,
	is_remediated BOOLEAN NOT NULL,
	remediated_at TIMESTAMP WITH TIME ZONE,
	remediated_by_id UUID,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	event_hash VARCHAR(64),
	prev_hash VARCHAR(64),
	PRIMARY KEY (id),
	FOREIGN KEY(audit_id) REFERENCES audits (id) ON DELETE CASCADE,
	FOREIGN KEY(remediated_by_id) REFERENCES users (id) ON DELETE SET NULL,
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX IF NOT EXISTS idx_audit_traces_tenant_id ON audit_traces(tenant_id);

CREATE TABLE IF NOT EXISTS enhanced_traces (
	id UUID NOT NULL,
	audit_id UUID NOT NULL,
	confidence FLOAT,
	model_version VARCHAR(100),
	executive_summary TEXT,
	chain_of_thought JSON NOT NULL,
	executive_steps JSON,
	client_input_summary JSON,
	client_output_summary JSON,
	raw_prompt TEXT,
	raw_response TEXT,
	prompt_text TEXT,
	raw_output_text TEXT,
	export_hash VARCHAR(64),
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (audit_id),
	FOREIGN KEY(audit_id) REFERENCES audits (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evf_engagement_transitions (
	id UUID NOT NULL,
	engagement_id UUID NOT NULL,
	from_state VARCHAR(50) NOT NULL,
	to_state VARCHAR(50) NOT NULL,
	actor_user_id UUID,
	reason TEXT,
	event_hash VARCHAR(64),
	prev_hash VARCHAR(64),
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(engagement_id) REFERENCES evf_sme_engagements (id) ON DELETE CASCADE,
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS evf_qco_registry (
	id UUID NOT NULL,
	qco_reference_number VARCHAR(100) NOT NULL,
	framework_covered VARCHAR(50) NOT NULL,
	saro_version_assessed VARCHAR(50) NOT NULL,
	sme_firm VARCHAR(255) NOT NULL,
	sme_credential VARCHAR(255),
	issue_date TIMESTAMP WITHOUT TIME ZONE,
	expiry_date TIMESTAMP WITHOUT TIME ZONE,
	scope_boundary_summary TEXT,
	document_url TEXT,
	document_sha256 VARCHAR(64),
	engagement_id UUID,
	published BOOLEAN NOT NULL,
	published_at TIMESTAMP WITH TIME ZONE,
	published_by_user_id UUID,
	prev_hash VARCHAR(64),
	record_hash VARCHAR(64),
	renews_qco_id UUID,
	superseded_by_qco_id UUID,
	created_by_user_id UUID,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (qco_reference_number),
	FOREIGN KEY(engagement_id) REFERENCES evf_sme_engagements (id) ON DELETE SET NULL,
	FOREIGN KEY(published_by_user_id) REFERENCES users (id) ON DELETE SET NULL,
	FOREIGN KEY(renews_qco_id) REFERENCES evf_qco_registry (id) ON DELETE SET NULL,
	FOREIGN KEY(superseded_by_qco_id) REFERENCES evf_qco_registry (id) ON DELETE SET NULL,
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS evf_validation_gates (
	id UUID NOT NULL,
	engagement_id UUID NOT NULL,
	coi_declared_approved BOOLEAN NOT NULL,
	coi_evidence_ref VARCHAR(500),
	sow_executed BOOLEAN NOT NULL,
	sow_evidence_ref VARCHAR(500),
	evidence_package_delivered BOOLEAN NOT NULL,
	evidence_package_ref VARCHAR(500),
	product_demo_completed BOOLEAN NOT NULL,
	product_demo_ref VARCHAR(500),
	draft_qco_received BOOLEAN NOT NULL,
	draft_qco_ref VARCHAR(500),
	saro_legal_review_completed BOOLEAN NOT NULL,
	legal_signoff_ref VARCHAR(500),
	qco_approved_ref_assigned BOOLEAN NOT NULL,
	qco_ref VARCHAR(100),
	locked BOOLEAN NOT NULL,
	locked_at TIMESTAMP WITH TIME ZONE,
	locked_by_user_id UUID,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (engagement_id),
	FOREIGN KEY(engagement_id) REFERENCES evf_sme_engagements (id) ON DELETE CASCADE,
	FOREIGN KEY(locked_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS github_scan_results (
	id UUID NOT NULL,
	audit_id UUID NOT NULL,
	repo_name VARCHAR(255) NOT NULL,
	file_path VARCHAR(500) NOT NULL,
	line_number INTEGER,
	snippet TEXT,
	correlation_note TEXT,
	finding_domain VARCHAR(255),
	scan_hash VARCHAR(64),
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(audit_id) REFERENCES audits (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS hf_sample_queue (
	id UUID NOT NULL,
	tenant_id UUID NOT NULL,
	vertical VARCHAR(50) NOT NULL,
	source_dataset VARCHAR(200) NOT NULL,
	prompt_text TEXT NOT NULL,
	raw_output_text TEXT NOT NULL,
	source_model VARCHAR(100) NOT NULL,
	status VARCHAR(20) NOT NULL,
	audit_id UUID,
	error_message TEXT,
	retry_count INTEGER NOT NULL,
	sampled_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	processed_at TIMESTAMP WITH TIME ZONE,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE,
	FOREIGN KEY(audit_id) REFERENCES audits (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS iso42001_documents (
	id UUID NOT NULL,
	audit_id UUID NOT NULL,
	generated_by_user_id UUID,
	format VARCHAR(20) NOT NULL,
	content TEXT NOT NULL,
	content_hash VARCHAR(64) NOT NULL,
	version INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(audit_id) REFERENCES audits (id) ON DELETE CASCADE,
	FOREIGN KEY(generated_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS risk_metadata (
	id UUID NOT NULL,
	audit_id UUID NOT NULL,
	owner VARCHAR(255),
	status_override VARCHAR(50),
	dismissed BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (audit_id),
	FOREIGN KEY(audit_id) REFERENCES audits (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sample_findings (
	id UUID NOT NULL,
	audit_id UUID NOT NULL,
	sample_id VARCHAR(255) NOT NULL,
	domain VARCHAR(255) NOT NULL,
	matched_signal VARCHAR(500) NOT NULL,
	matched_text_fragment VARCHAR(200),
	weight FLOAT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(audit_id) REFERENCES audits (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS scan_reports (
	id UUID NOT NULL,
	audit_id UUID NOT NULL,
	tenant_id UUID,
	mit_coverage_score FLOAT,
	fixed_delta FLOAT,
	overall_risk_score FLOAT,
	confidence_score FLOAT,
	report_json JSON NOT NULL,
	engine_version VARCHAR(50),
	rule_pack_hash VARCHAR(64),
	compliance_matrix_version VARCHAR(100),
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (audit_id),
	FOREIGN KEY(audit_id) REFERENCES audits (id) ON DELETE CASCADE,
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE INDEX IF NOT EXISTS idx_scan_reports_tenant_id ON scan_reports(tenant_id);

CREATE TABLE IF NOT EXISTS system_audits (
	id UUID NOT NULL,
	system_id UUID NOT NULL,
	audit_id UUID NOT NULL,
	linked_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(system_id) REFERENCES ai_systems (id) ON DELETE CASCADE,
	FOREIGN KEY(audit_id) REFERENCES audits (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evf_expiry_notifications (
	id UUID NOT NULL,
	qco_id UUID,
	qco_reference_number VARCHAR(100) NOT NULL,
	framework VARCHAR(50) NOT NULL,
	notification_type VARCHAR(20) NOT NULL,
	expires_in_days INTEGER,
	sent_at TIMESTAMP WITH TIME ZONE NOT NULL,
	idempotency_key VARCHAR(255) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(qco_id) REFERENCES evf_qco_registry (id) ON DELETE SET NULL,
	UNIQUE (idempotency_key)
);
