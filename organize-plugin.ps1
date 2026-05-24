# organize-plugin.ps1
# Run from your SARO repo root: .\organize-plugin.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== SARO Plugin File Organizer ===" -ForegroundColor Green

# Create directory structure
$dirs = @(
    "saro-platform\.claude-plugin",
    "saro-platform\.claude\hooks",
    "saro-platform\.claude\subagents",
    "saro-platform\commands",
    "saro-platform\skills",
    "saro-platform\docs\decisions",
    "saro-platform\docs\runbooks",
    "saro-platform\tools\scripts",
    "saro-platform\tools\prompts"
)

foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Write-Host "  Created: $dir"
}

# Move files to correct locations
$moves = @{
    "plugin.json"                    = "saro-platform\.claude-plugin\plugin.json"
    "settings.json"                  = "saro-platform\.claude\settings.json"
    "pre-edit-standards-check.sh"    = "saro-platform\.claude\hooks\pre-edit-standards-check.sh"
    "pre-commit-compliance-gate.sh"  = "saro-platform\.claude\hooks\pre-commit-compliance-gate.sh"
    "post-edit-version-check.sh"     = "saro-platform\.claude\hooks\post-edit-version-check.sh"
    "drift-agent.md"                 = "saro-platform\.claude\subagents\drift-agent.md"
    "compliance-agent.md"            = "saro-platform\.claude\subagents\compliance-agent.md"
    "report-agent.md"                = "saro-platform\.claude\subagents\report-agent.md"
    "ADR-004-compliance-scope-locks.md" = "saro-platform\docs\decisions\ADR-004-compliance-scope-locks.md"
    "RB-005-enterprise-demo-prep.md" = "saro-platform\docs\runbooks\RB-005-enterprise-demo-prep.md"
    "health-check.sh"                = "saro-platform\tools\scripts\health-check.sh"
    "system-prompts.md"              = "saro-platform\tools\prompts\system-prompts.md"
}

Write-Host "`nMoving files..." -ForegroundColor Yellow
foreach ($src in $moves.Keys) {
    $dest = $moves[$src]
    if (Test-Path $src) {
        Move-Item -Path $src -Destination $dest -Force
        Write-Host "  $src -> $dest"
    } else {
        Write-Host "  SKIP (not found): $src" -ForegroundColor Red
    }
}

# Git add and commit
Write-Host "`nStaging files..." -ForegroundColor Yellow
git add saro-platform/

Write-Host "`nCommitting..." -ForegroundColor Yellow
git commit -m "feat: add saro-platform Claude plugin (5-layer AI OS)

- Layer 01 Memory: skills/codebase-standards.md + settings.json
- Layer 02 Knowledge: 6 domain skill files (compliance, team, deployment, arch, QA)
- Layer 03 Guardrails: 3 hooks (pre-edit, pre-commit, post-edit)
- Layer 04 Delegation: DriftAgent, ComplianceAgent, ReportAgent subagents
- Layer 05 Distribution: plugin manifest + MCP connections
- docs/decisions: ADR-004 compliance scope locks
- docs/runbooks: RB-005 enterprise demo pre-flight
- tools/scripts: health-check.sh
- tools/prompts: 4 reusable Claude API system prompts"

Write-Host "`nPushing..." -ForegroundColor Yellow
git push origin main

Write-Host "`n=== Done ===" -ForegroundColor Green
