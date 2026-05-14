-- Enable RLS on all tenant-scoped tables
ALTER TABLE audits ENABLE ROW LEVEL SECURITY;
ALTER TABLE scan_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_traces ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY tenant_isolation_audits ON audits
  USING (tenant_id::text = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_scan_reports ON scan_reports
  USING (tenant_id::text = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_audit_traces ON audit_traces
  USING (tenant_id::text = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_users ON users
  USING (tenant_id::text = current_setting('app.current_tenant', true));

-- Allow super_admin bypass
CREATE POLICY super_admin_all_audits ON audits
  USING (current_setting('app.is_super_admin', true) = 'true');
