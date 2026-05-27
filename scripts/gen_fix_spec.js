/**
 * SARO Fix Specification v1.0 — docx generator
 * Run: node scripts/gen_fix_spec.js
 * Output: docs/SARO_Fix_Spec_v1.0.docx
 */
"use strict";
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  PageBreak, LevelFormat
} = require("docx");
const fs = require("fs");
const path = require("path");

// ── Palette ──────────────────────────────────────────────────────────────────
const C = {
  teal:       "0D7A75",
  tealLight:  "E0F4F3",
  dark:       "1F2937",
  gray:       "6B7280",
  redBg:      "FEE2E2",
  yellowBg:   "FEF9C3",
  greenBg:    "DCFCE7",
  blueBg:     "DBEAFE",
  white:      "FFFFFF",
  border:     "D1D5DB",
  codeBg:     "F3F4F6",
};

// ── Helpers ───────────────────────────────────────────────────────────────────
const B = (style, color, fill) => ({ style, size: 1, color, fill });
const borders = (col = C.border) => {
  const b = B(BorderStyle.SINGLE, col);
  return { top: b, bottom: b, left: b, right: b };
};
const cellMargins = { top: 80, bottom: 80, left: 140, right: 140 };

function para(text, opts = {}) {
  const { bold = false, size = 22, color, indent = 0, before = 80, after = 80,
          italic = false, font = "Arial" } = opts;
  return new Paragraph({
    children: [new TextRun({ text, bold, size, color, italics: italic, font })],
    indent: indent ? { left: indent } : undefined,
    spacing: { before, after },
    alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT,
  });
}

function code(text, opts = {}) {
  const lines = text.split("\n");
  return lines.map(line =>
    new Paragraph({
      children: [new TextRun({ text: line || " ", font: "Courier New", size: 18, color: C.dark })],
      indent: { left: opts.indent ?? 560 },
      spacing: { before: 0, after: 0 },
      shading: { fill: C.codeBg, type: ShadingType.CLEAR },
    })
  );
}

function codeBlock(text, opts = {}) {
  const lines = text.split("\n");
  return lines.map((line, i) =>
    new Paragraph({
      children: [new TextRun({ text: line || " ", font: "Courier New", size: 17, color: C.dark })],
      indent: { left: 560 },
      spacing: { before: 0, after: 0 },
      border: {
        top:    i === 0                   ? B(BorderStyle.SINGLE, C.border) : undefined,
        bottom: i === lines.length - 1    ? B(BorderStyle.SINGLE, C.border) : undefined,
        left:   B(BorderStyle.THICK,  C.teal),
        right:  B(BorderStyle.SINGLE, C.border),
      },
      shading: { fill: C.codeBg, type: ShadingType.CLEAR },
    })
  );
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text, bold: true, size: 36, color: C.teal, font: "Arial" })],
    spacing: { before: 400, after: 180 },
    border: { bottom: B(BorderStyle.SINGLE, C.teal) },
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text, bold: true, size: 28, color: C.dark, font: "Arial" })],
    spacing: { before: 280, after: 120 },
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    children: [new TextRun({ text, bold: true, size: 24, color: C.dark, font: "Arial" })],
    spacing: { before: 200, after: 100 },
  });
}

function h4(text) {
  return new Paragraph({
    children: [new TextRun({ text, bold: true, size: 22, color: C.gray, font: "Arial" })],
    spacing: { before: 160, after: 80 },
  });
}

function bullet(text, opts = {}) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children: [new TextRun({ text, size: 22, font: "Arial", bold: opts.bold })],
    spacing: { before: 60, after: 60 },
  });
}

function numbered(text) {
  return new Paragraph({
    numbering: { reference: "numbers", level: 0 },
    children: [new TextRun({ text, size: 22, font: "Arial" })],
    spacing: { before: 60, after: 60 },
  });
}

function pb() {
  return new Paragraph({ children: [new PageBreak()] });
}

function spacer(n = 1) {
  return new Paragraph({
    children: [new TextRun({ text: " " })],
    spacing: { before: n * 60, after: n * 60 },
  });
}

function statusCell(text, fill, bold = false) {
  return new TableCell({
    borders: borders(),
    shading: { fill, type: ShadingType.CLEAR },
    margins: cellMargins,
    width: { size: 1800, type: WidthType.DXA },
    children: [new Paragraph({ children: [new TextRun({ text, bold, size: 20, font: "Arial" })] })],
  });
}

function dataCell(text, fill = C.white, bold = false, width = 5000) {
  return new TableCell({
    borders: borders(),
    shading: { fill, type: ShadingType.CLEAR },
    margins: cellMargins,
    width: { size: width, type: WidthType.DXA },
    children: [new Paragraph({ children: [new TextRun({ text, bold, size: 20, font: "Arial" })] })],
  });
}

function headerCell(text, width = 4680) {
  return new TableCell({
    borders: borders(C.teal),
    shading: { fill: C.teal, type: ShadingType.CLEAR },
    margins: cellMargins,
    width: { size: width, type: WidthType.DXA },
    children: [new Paragraph({ children: [new TextRun({ text, bold: true, size: 20, color: C.white, font: "Arial" })] })],
  });
}

function twoColTable(pairs, col1 = 2800, col2 = 6560) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [col1, col2],
    rows: pairs.map(([k, v, isHeader]) => new TableRow({
      tableHeader: !!isHeader,
      children: [
        isHeader ? headerCell(k, col1) : new TableCell({
          borders: borders(),
          shading: { fill: C.codeBg, type: ShadingType.CLEAR },
          margins: cellMargins,
          width: { size: col1, type: WidthType.DXA },
          children: [new Paragraph({ children: [new TextRun({ text: k, bold: true, size: 20, font: "Arial", color: C.dark })] })],
        }),
        isHeader ? headerCell(v, col2) : dataCell(v, C.white, false, col2),
      ],
    })),
  });
}

function scorecardRow(story, status, issue) {
  const fill = status.includes("PASS") ? C.greenBg : status.includes("FAIL") ? C.redBg : C.yellowBg;
  return new TableRow({ children: [
    dataCell(story, C.white, true, 1200),
    dataCell(status, fill, true, 2000),
    dataCell(issue, C.white, false, 6160),
  ]});
}

// ── Build: Cover Page ─────────────────────────────────────────────────────────
function coverPage() {
  return [
    spacer(6),
    new Paragraph({
      children: [new TextRun({ text: "SARO", bold: true, size: 96, color: C.teal, font: "Arial" })],
      alignment: AlignmentType.CENTER,
    }),
    new Paragraph({
      children: [new TextRun({ text: "Smart AI Risk Orchestrator", size: 36, color: C.gray, font: "Arial" })],
      alignment: AlignmentType.CENTER,
      spacing: { before: 80, after: 80 },
    }),
    spacer(2),
    new Paragraph({
      children: [new TextRun({ text: "Fix Specification v1.0", bold: true, size: 52, color: C.dark, font: "Arial" })],
      alignment: AlignmentType.CENTER,
      spacing: { before: 120, after: 80 },
    }),
    new Paragraph({
      children: [new TextRun({ text: "Based on Spec v1.1 Audit  |  May 2026  |  5 Critical Fixes  |  12 Stories Remediated", size: 22, color: C.gray, font: "Arial" })],
      alignment: AlignmentType.CENTER,
      spacing: { before: 80, after: 80 },
    }),
    spacer(2),
    new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: [4680, 4680],
      rows: [
        new TableRow({ children: [headerCell("Fix", 4680), headerCell("Story Reference", 4680)] }),
        new TableRow({ children: [dataCell("FIX-001  URL Alignment", C.white, false, 4680), dataCell("S-003 · S-303", C.white, false, 4680)] }),
        new TableRow({ children: [dataCell("FIX-002  fly.toml auto_stop", C.white, false, 4680), dataCell("S-301", C.white, false, 4680)] }),
        new TableRow({ children: [dataCell("FIX-003  Demo JWT + Write Guard", C.white, false, 4680), dataCell("S-205", C.white, false, 4680)] }),
        new TableRow({ children: [dataCell("FIX-004  model_version null gate", C.white, false, 4680), dataCell("S-202", C.white, false, 4680)] }),
        new TableRow({ children: [dataCell("FIX-005  React Frontend Dashboard", C.white, false, 4680), dataCell("S-201", C.white, false, 4680)] }),
      ],
    }),
    spacer(2),
    new Paragraph({
      children: [new TextRun({ text: "Contract Compliance Tests: S-000 · S-002 · S-003 · S-101 · S-103 · S-202 · S-203 · S-204 · S-205 · S-301 · S-302 · S-303", size: 20, color: C.gray, font: "Arial", italics: true })],
      alignment: AlignmentType.CENTER,
    }),
    pb(),
  ];
}

// ── Build: Audit Summary ──────────────────────────────────────────────────────
function auditSummary() {
  return [
    h1("Section 1 — Audit Summary"),
    para("The following table records the implementation status of every Spec v1.1 story as found by the May 2026 audit. This specification targets every story marked PARTIAL or FAIL."),
    spacer(),
    new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: [1200, 2000, 6160],
      rows: [
        new TableRow({ tableHeader: true, children: [
          headerCell("Story", 1200), headerCell("Status", 2000), headerCell("Blocking Issue", 6160),
        ]}),
        scorecardRow("S-000", "⚠️ PARTIAL", "field names diverged from spec; .env.demo not in .gitignore"),
        scorecardRow("S-001", "✅ PASS", "—"),
        scorecardRow("S-002", "⚠️ PARTIAL", "--count arg missing; wrong dataset registry for healthcare"),
        scorecardRow("S-003", "❌ FAIL", "Wrong URL (/hf/process vs /hf-processor/run); CI workflow will 404"),
        scorecardRow("S-101", "⚠️ PARTIAL", "Field names prompt/raw_output vs spec prompt_text/raw_output_text; read_only guard missing"),
        scorecardRow("S-102", "✅ PASS", "trace_url path differs consistently with S-101"),
        scorecardRow("S-103", "⚠️ PARTIAL", "Only Python snippet; JSON wrapper instead of PlainTextResponse"),
        scorecardRow("S-201", "❌ NOT DONE", "No React frontend exists — production serves Streamlit"),
        scorecardRow("S-202", "⚠️ PARTIAL", "Wrong URL; model_version hardcoded 'saro-engine-1.0'; no cross-tenant guard"),
        scorecardRow("S-203", "⚠️ PARTIAL", "URL hyphen vs underscore; coverage from static data not audit_traces; no window param"),
        scorecardRow("S-204", "⚠️ PARTIAL", "PATCH URL and payload differ from spec; no gate filter"),
        scorecardRow("S-205", "⚠️ PARTIAL", "Backend token endpoint done but JWT sub=tenant_id breaks get_current_user; write guard not applied"),
        scorecardRow("S-301", "❌ FAIL", "auto_stop_machines=true; deployment not live (ECONNREFUSED)"),
        scorecardRow("S-302", "⚠️ PARTIAL", "Missing migration step; health-check URL does not match fly.toml app name"),
        scorecardRow("S-303", "❌ FAIL", "Processor URL 404 — daily sampler enqueues rows but never processes them"),
      ],
    }),
    spacer(2),
    h2("Production Environment"),
    twoColTable([
      ["Check", "Result", true],
      ["saro-production-2993.up.railway.app/health", "Returns Streamlit HTML — FastAPI not accessible at this URL"],
      ["saro-platform.fly.dev/health", "ECONNREFUSED — Fly.io app is not running"],
      ["Tests (local)", "62 / 62 pass — but tests verify implementation, not spec contract"],
    ]),
    pb(),
  ];
}

// ── Build: Global Rules ───────────────────────────────────────────────────────
function globalRules() {
  return [
    h1("Section 2 — Claude Code Global Rules (applies to every fix)"),
    para("These rules override any other instruction. Read ALL rules before starting any fix.", { bold: true }),
    spacer(),
    h2("2.1  Read-Before-Write"),
    para("Before writing code for any fix, read these files from the actual repo:"),
    ...["routers/hf_processor.py", "routers/ingest.py", "routers/demo.py", "auth.py",
        "fly.toml", ".github/workflows/hf_sampler.yml", ".github/workflows/deploy.yml",
        "routers/trace_view.py", "routers/compliance_matrix.py"].map(f => bullet(f)),
    spacer(),
    h2("2.2  Output Format"),
    para("Every coding response MUST end with this exact block:", { bold: true }),
    ...codeBlock(
`FILES CHANGED:
  - path/to/file.py  (what changed and why)
FILES NOT TOUCHED:
  - path/to/other.py
MIGRATIONS NEEDED:
  - migrations/NNN_description.sql  (exact SQL, or 'none')
CONCERNS:
  - Any assumption made due to unreadable file
  - Any unresolved VERIFY flag`
    ),
    spacer(),
    h2("2.3  Integration Rules"),
    bullet("Never create standalone repos, separate folders, or parallel implementations"),
    bullet("All schemas stay in schemas.py or inline in the router that owns them — never scattered across new files"),
    bullet("Use the existing get_db session dependency — never a new DB session pattern"),
    bullet("Use the existing get_current_user JWT dependency — never create new auth"),
    bullet("Use FastAPI BackgroundTasks — never threading.Thread or asyncio.create_task"),
    bullet("Use structlog for all logging — never print() or logging.info()"),
    spacer(),
    h2("2.4  Safety Rules"),
    bullet("Never DROP TABLE or DROP COLUMN without Venky confirmation"),
    bullet("Every ALTER TABLE must be wrapped in a transaction with a rollback comment"),
    bullet("Never use Alembic autogenerate — write explicit SQL"),
    bullet("Never skip CI hooks or push --force to main"),
    bullet("Never store the demo JWT in localStorage — sessionStorage only (S-205)"),
    pb(),
  ];
}

// ── FIX-001 ───────────────────────────────────────────────────────────────────
function fix001() {
  return [
    h1("Section 3 — Fix Stories"),
    h2("FIX-001  |  S-003 / S-303 — Endpoint URL Alignment"),
    twoColTable([
      ["Priority", "P0 — Critical (breaks daily pipeline)"],
      ["Owner",    "Jordan Lee"],
      ["Depends",  "None — standalone rename"],
      ["Affects",  "routers/hf_processor.py · .github/workflows/hf_sampler.yml · tests/test_s003_hf_processor.py"],
    ], 1800, 7560),
    spacer(),
    h3("Problem"),
    para("The hf_processor router uses prefix /api/v1/hf with endpoints /process and /queue/status. The spec, test files, and CI workflow all reference /api/v1/hf-processor/run and /api/v1/hf-processor/status. Every daily sampler run enqueues rows that are never processed because the trigger POST hits a 404."),
    spacer(),
    h3("VERIFY — read before coding"),
    twoColTable([
      ["File", "What to confirm", true],
      ["routers/hf_processor.py:36", "Current prefix is /api/v1/hf — confirm before rename"],
      ["routers/hf_processor.py:186", "POST endpoint path is /process — confirm before rename"],
      ["routers/hf_processor.py:242", "GET endpoint path is /queue/status — confirm before rename"],
      [".github/workflows/hf_sampler.yml:63", "URL called is /api/v1/hf-processor/run — confirm before fixing workflow"],
      ["main.py:249", "hf_processor_router registration line — confirm no prefix override"],
    ], 3000, 6360),
    spacer(),
    h3("Code Changes"),
    h4("routers/hf_processor.py — three changes"),
    para("Change 1: router prefix (line 36)"),
    ...codeBlock(
`# FROM:
router = APIRouter(prefix="/api/v1/hf", tags=["hf-processor"])

# TO:
router = APIRouter(prefix="/api/v1/hf-processor", tags=["hf-processor"])`
    ),
    spacer(),
    para("Change 2: POST endpoint path (line 186)"),
    ...codeBlock(
`# FROM:
@router.post(
    "/process",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Process pending HuggingFace sample queue rows",
)
def trigger_hf_processing(

# TO:
@router.post(
    "/run",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Process pending HuggingFace sample queue rows",
)
def trigger_hf_processing(`
    ),
    spacer(),
    para("Change 3: GET endpoint path (line 242)"),
    ...codeBlock(
`# FROM:
@router.get(
    "/queue/status",
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Get HuggingFace sample queue status counts",
)
def get_queue_status(

# TO:
@router.get(
    "/status",
    dependencies=[Depends(require_role("super_admin", "operator"))],
    summary="Get HuggingFace sample queue status counts",
)
def get_queue_status(`
    ),
    spacer(),
    h4(".github/workflows/hf_sampler.yml — update processor trigger URL"),
    para("The hf_sampler.yml workflow already uses the correct spec URL. After FIX-001 renames the endpoint, the workflow will work correctly. No change needed to the workflow file IF FIX-001 is applied to the router. Verify the trigger step still reads:"),
    ...codeBlock(
`# .github/workflows/hf_sampler.yml  (verify — no change needed if router is fixed)
# Step: Trigger processor
run: |
  curl -X POST \\
    "$SARO_URL/api/v1/hf-processor/run?tenant_id=$SARO_DEMO_TENANT_ID" \\
    -H "Authorization: Bearer $SARO_BEARER" \\
    -w "\\nHTTP %{http_code}\\n"`
    ),
    spacer(),
    h3("Acceptance Criteria"),
    numbered("POST /api/v1/hf-processor/run returns 202 with pending_count and message fields"),
    numbered("GET /api/v1/hf-processor/status returns counts: pending, processing, processed, failed, total"),
    numbered("Old paths /api/v1/hf/process and /api/v1/hf/queue/status return 404 — no backwards-compat aliases"),
    numbered("GitHub Actions hf_sampler.yml trigger step returns HTTP 202 (not 404)"),
    numbered("All existing S-003 tests pass against the renamed endpoints"),
    numbered("OpenAPI docs at /docs show the new paths"),
    spacer(),
    h3("Test Cases — tests/test_s003_hf_processor.py (update existing file)"),
    ...codeBlock(
`# tests/test_s003_hf_processor.py
# Update: change all endpoint references from /api/v1/hf/ to /api/v1/hf-processor/

import pytest
from httpx import AsyncClient
from models import HFSampleQueue, HFSampleStatus

# VERIFY: auth_client fixture provides authenticated async HTTPX client
# VERIFY: demo_tenant fixture provides a Tenant ORM object

async def test_run_endpoint_exists(auth_client, demo_tenant, db_session):
    """POST /api/v1/hf-processor/run must return 202, not 404."""
    resp = await auth_client.post("/api/v1/hf-processor/run")
    assert resp.status_code != 404, "Endpoint renamed — old /hf/process is gone"
    assert resp.status_code in (200, 202)

async def test_run_returns_202_with_pending_count(auth_client, demo_tenant, db_session):
    for _ in range(3):
        db_session.add(HFSampleQueue(
            tenant_id=demo_tenant.id, vertical="finance",
            source_dataset="test", prompt_text="Q", raw_output_text="A",
            source_model="unknown",
        ))
    db_session.commit()
    resp = await auth_client.post("/api/v1/hf-processor/run")
    assert resp.status_code == 202
    data = resp.json()
    assert "pending_count" in data
    assert data["pending_count"] >= 3

async def test_status_endpoint_exists(auth_client):
    """GET /api/v1/hf-processor/status must return 200, not 404."""
    resp = await auth_client.get("/api/v1/hf-processor/status")
    assert resp.status_code != 404, "Endpoint renamed — old /hf/queue/status is gone"
    assert resp.status_code == 200

async def test_status_returns_all_count_keys(auth_client, demo_tenant, db_session):
    resp = await auth_client.get("/api/v1/hf-processor/status")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) >= {"pending", "processing", "processed", "failed", "total"}

async def test_old_process_path_returns_404(auth_client):
    """Old URL must be gone — no silent backwards-compat alias."""
    resp = await auth_client.post("/api/v1/hf/process")
    assert resp.status_code == 404

async def test_old_queue_status_path_returns_404(auth_client):
    resp = await auth_client.get("/api/v1/hf/queue/status")
    assert resp.status_code == 404

async def test_unauthenticated_run_returns_401(client):
    resp = await client.post("/api/v1/hf-processor/run")
    assert resp.status_code == 401

async def test_unauthenticated_status_returns_401(client):
    resp = await client.get("/api/v1/hf-processor/status")
    assert resp.status_code == 401`
    ),
    pb(),
  ];
}

// ── FIX-002 ───────────────────────────────────────────────────────────────────
function fix002() {
  return [
    h2("FIX-002  |  S-301 — fly.toml auto_stop_machines"),
    twoColTable([
      ["Priority", "P0 — Critical (cold-start kills live demos)"],
      ["Owner",    "Venky"],
      ["Depends",  "None — one-line change"],
      ["Affects",  "fly.toml · .github/workflows/deploy.yml (health-check URL)"],
    ], 1800, 7560),
    spacer(),
    h3("Problem"),
    para("fly.toml has auto_stop_machines = true. The entire purpose of S-301 was to eliminate Railway cold-start instability — this setting re-enables it. The app goes to sleep between requests and may not wake in time for a client demo. Additionally the app name is saro-api but the CI health-check job pings saro-platform.fly.dev, which will not match the deployed app."),
    spacer(),
    h3("VERIFY — read before coding"),
    twoColTable([
      ["File", "What to confirm", true],
      ["fly.toml:18",   "auto_stop_machines = true — confirm value before changing"],
      ["fly.toml:5",    "app = saro-api — confirm app name"],
      ["fly.toml:6",    "primary_region = lhr — note: spec said dfw; verify with Venky before changing region"],
      [".github/workflows/deploy.yml:78", "Health-check pings saro-platform.fly.dev — must match fly.toml app name"],
    ], 3200, 6160),
    spacer(),
    h3("Code Changes"),
    h4("fly.toml — two changes"),
    para("Change 1: disable auto-stop (line 18)"),
    ...codeBlock(
`# FROM:
  auto_stop_machines  = true

# TO:
  auto_stop_machines  = false`
    ),
    spacer(),
    para("Change 2: add [[http_service.checks]] block (add after min_machines_running line if not present)"),
    ...codeBlock(
`# ADD after min_machines_running = 1:
  [[http_service.checks]]
    grace_period  = "10s"
    interval      = "30s"
    method        = "GET"
    path          = "/health"
    protocol      = "http"
    timeout       = "5s"
    tls_skip_verify = false`
    ),
    spacer(),
    h4(".github/workflows/deploy.yml — fix health-check URL"),
    para("The health-check job pings saro-platform.fly.dev but fly.toml deploys the app as saro-api. Change the health-check URL to match the actual deployed app name OR align fly.toml app name with the workflow. Verify with Venky which app name is canonical."),
    ...codeBlock(
`# .github/workflows/deploy.yml
# Change the health-check step URL to match fly.toml app name.
# If fly.toml app = "saro-api" then:

# FROM:
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \\
         https://saro-platform.fly.dev/health)

# TO (if app name stays saro-api):
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \\
         https://saro-api.fly.dev/health)

# OR (if Venky wants canonical URL to be saro-platform):
# Change fly.toml: app = "saro-platform"
# VERIFY with Venky before making this decision`
    ),
    spacer(),
    h3("Acceptance Criteria"),
    numbered("fly.toml has auto_stop_machines = false — verified with: grep auto_stop fly.toml"),
    numbered("fly deploy succeeds without manual steps — zero 5xx errors during deploy"),
    numbered("GET /health returns {status: 'ok'} within 3 seconds at any time — including after 30 minutes of idle"),
    numbered("fly status shows min_machines_running = 1 and at least one machine in 'started' state"),
    numbered("CI health-check job URL matches the fly.toml app name — no URL mismatch"),
    numbered("fly machines list shows auto_stop = false for all machines"),
    spacer(),
    h3("Test Cases — tests/test_s301_fly.py (new file)"),
    ...codeBlock(
`# tests/test_s301_fly.py
# Unit-level checks — no live Fly.io connection required.
# Integration checks marked @pytest.mark.integration run only in ENVIRONMENT=integration.

import pytest
import toml   # pip install toml if not present; add to requirements.txt

FLY_TOML_PATH = "fly.toml"

def test_fly_toml_exists():
    """fly.toml must be present at repo root."""
    import os
    assert os.path.exists(FLY_TOML_PATH), "fly.toml missing from repo root"

def test_auto_stop_machines_is_false():
    """Critical: auto_stop_machines must be false to prevent cold-start."""
    with open(FLY_TOML_PATH) as f:
        content = f.read()
    # Simple string check — toml parse would be cleaner but this is robust
    assert "auto_stop_machines  = false" in content or \\
           "auto_stop_machines = false" in content, \\
        "auto_stop_machines must be false — found true in fly.toml"

def test_min_machines_running_is_one():
    with open(FLY_TOML_PATH) as f:
        content = f.read()
    assert "min_machines_running = 1" in content, \\
        "min_machines_running must be 1 to ensure always-on"

def test_health_check_path_configured():
    with open(FLY_TOML_PATH) as f:
        content = f.read()
    assert 'path          = "/health"' in content or \\
           'path = "/health"' in content, \\
        "Health check path /health must be configured in fly.toml"

def test_deploy_yml_health_check_url_matches_app_name():
    """CI health-check URL must match fly.toml app name."""
    import re
    with open(FLY_TOML_PATH) as f:
        fly_content = f.read()
    app_match = re.search(r'app\\s*=\\s*"([^"]+)"', fly_content)
    assert app_match, "Could not find app name in fly.toml"
    app_name = app_match.group(1)

    with open(".github/workflows/deploy.yml") as f:
        deploy_content = f.read()
    expected_url_fragment = f"https://{app_name}.fly.dev/health"
    assert expected_url_fragment in deploy_content, \\
        f"CI health-check URL must contain '{expected_url_fragment}' — app name mismatch"

@pytest.mark.integration
def test_health_endpoint_responds(production_url):
    """Integration: /health responds within 3 seconds at any time."""
    import requests, time
    start = time.monotonic()
    resp = requests.get(f"{production_url}/health", timeout=3)
    elapsed = time.monotonic() - start
    assert resp.status_code == 200, f"Health check returned {resp.status_code}"
    assert elapsed < 3.0, f"Health check took {elapsed:.1f}s — exceeds 3s SLA"
    data = resp.json()
    assert data.get("status") == "ok" or data.get("db_ok") is True`
    ),
    pb(),
  ];
}

// ── FIX-003 ───────────────────────────────────────────────────────────────────
function fix003() {
  return [
    h2("FIX-003  |  S-205 — Demo JWT + Write Guard"),
    twoColTable([
      ["Priority", "P0 — Critical (demo security + functionality both broken)"],
      ["Owner",    "Venky + Jordan Lee"],
      ["Depends",  "S-000 must have run seed_demo_tenant.py to create demo user in DB"],
      ["Affects",  "routers/demo.py · routers/ingest.py · routers/hf_processor.py · auth.py"],
    ], 1800, 7560),
    spacer(),
    h3("Problem (two issues)"),
    para("Issue A — JWT sub claim is wrong:", { bold: true }),
    para("The demo JWT sets sub = SARO_DEMO_TENANT_ID (a tenant UUID). auth.py's get_current_user does db.get(User, user_id) where user_id = payload['sub']. A tenant UUID is not a user UUID — this lookup will return None and every demo-token request returns 401 'User not found'. The demo token is entirely non-functional."),
    spacer(),
    para("Issue B — write guard not applied:", { bold: true }),
    para("require_write_access exists in routers/demo.py but is never imported or applied to POST /ingest or POST /hf-processor/run. A demo token (if it were functional) could call any write endpoint."),
    spacer(),
    h3("VERIFY — read before coding"),
    twoColTable([
      ["File", "What to confirm", true],
      ["auth.py:155-165",    "get_current_user does db.get(User, payload['sub']) — confirm sub must be a User.id UUID"],
      ["routers/demo.py:154", "payload['sub'] = demo_tenant_id — confirm this is the bug"],
      ["models.py",          "User.role column — confirm 'demo_viewer' is a valid enum value, add if not"],
      ["models.py",          "User.read_only column — confirm it does NOT exist (it is a JWT claim, not a DB column)"],
      ["scripts/seed_demo_tenant.py", "Confirm a User row is created for the demo tenant — need that user's id for the JWT sub"],
      ["routers/ingest.py:180",       "POST /ingest dependencies list — confirm require_write_access is absent"],
      ["routers/hf_processor.py:186", "POST /run (after FIX-001) — confirm require_write_access is absent"],
    ], 3200, 6160),
    spacer(),
    h3("Code Changes"),
    h4("Part A — Fix JWT sub in routers/demo.py"),
    para("The get_demo_token function must look up the demo user from the database (not just use the tenant UUID) and use the user's actual id as the JWT sub claim. The user was created by seed_demo_tenant.py with email demo@saro-platform.io."),
    ...codeBlock(
`# routers/demo.py
# REPLACE get_demo_token with this implementation

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User
from typing import Annotated

@router.get(
    "/token",
    summary="Issue a 4-hour read-only demo JWT (public endpoint — no auth required)",
)
def get_demo_token(
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """
    Public endpoint — no auth required.
    Issues a short-lived (4h) read-only JWT for the demo tenant.
    JWT carries read_only=True so write endpoints can block it.

    Requires:
      1. SARO_DEMO_TENANT_ID env var (set by seed_demo_tenant.py)
      2. A User row in the DB with email demo@saro-platform.io
         (created by seed_demo_tenant.py Step 1)
    """
    import os
    from datetime import timedelta

    demo_tenant_id = os.getenv("SARO_DEMO_TENANT_ID")
    if not demo_tenant_id:
        raise HTTPException(
            status_code=503,
            detail="Demo tenant not configured — run scripts/seed_demo_tenant.py first",
        )

    # CRITICAL FIX: look up the demo user's actual UUID — do not use tenant_id as sub
    # get_current_user in auth.py does db.get(User, sub) so sub MUST be a User.id
    demo_user = (
        db.query(User)
        .filter(
            User.tenant_id == demo_tenant_id,
            User.email == "demo@saro-platform.io",
        )
        .first()
    )
    if not demo_user:
        raise HTTPException(
            status_code=503,
            detail=(
                "Demo user not found. "
                "Run scripts/seed_demo_tenant.py to create the demo tenant and user."
            ),
        )

    from auth import _secret_key, _algorithm
    from jose import jwt as _jwt

    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub":        str(demo_user.id),      # FIXED: user UUID, not tenant UUID
        "tenant_id":  demo_tenant_id,
        "role":       demo_user.role,          # real role from DB ("super_admin" for demo user)
        "read_only":  True,                    # write endpoints check this claim
        "exp":        now + timedelta(hours=4),
        "iat":        now,
    }
    token = _jwt.encode(payload, _secret_key(), algorithm=_algorithm())
    logger.info("demo_token_issued", user_id=str(demo_user.id))
    return {
        "access_token":     token,
        "token_type":       "bearer",
        "expires_in_hours": 4,
        "read_only":        True,
    }`
    ),
    spacer(),
    h4("Part B — Fix get_current_user to pass read_only claim through (auth.py)"),
    para("get_current_user returns a User ORM object. read_only is a JWT claim, not a DB column. The function must attach the claim to the user object so require_write_access can check it."),
    ...codeBlock(
`# auth.py
# REPLACE get_current_user with this version

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """
    Validate the Bearer token and return the authenticated User row.
    Attaches JWT claims (read_only, tenant_id) as transient attributes
    so downstream dependencies can check them without re-decoding the token.
    """
    payload = _decode_token(credentials.credentials)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Malformed token")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Account disabled")

    # Attach JWT claims as transient attributes (not persisted to DB)
    # This allows require_write_access to check read_only without re-decoding the token
    user.read_only = payload.get("read_only", False)   # type: ignore[attr-defined]

    return user`
    ),
    spacer(),
    h4("Part C — Apply require_write_access to write endpoints"),
    para("require_write_access is already defined in routers/demo.py. Add it to POST /ingest and POST /hf-processor/run. Because it also calls get_current_user, FastAPI's dependency cache ensures get_current_user runs only once per request."),
    ...codeBlock(
`# routers/ingest.py — ADD import at top
from routers.demo import require_write_access

# MODIFY POST /ingest dependencies (line ~181):
@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_role("super_admin", "operator")),
        Depends(require_write_access),         # ADD: block demo tokens
    ],
    summary="Ingest a single AI output for asynchronous SARO audit",
)
def ingest_output(
    payload: IngestRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> IngestResponse:`
    ),
    spacer(),
    ...codeBlock(
`# routers/hf_processor.py — ADD import at top (after FIX-001 rename)
from routers.demo import require_write_access

# MODIFY POST /run dependencies:
@router.post(
    "/run",                                    # after FIX-001 rename
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[
        Depends(require_role("super_admin", "operator")),
        Depends(require_write_access),         # ADD: block demo tokens
    ],
    summary="Process pending HuggingFace sample queue rows",
)
def trigger_hf_processing(`
    ),
    spacer(),
    h3("Acceptance Criteria"),
    numbered("GET /api/v1/demo/token returns 200 with access_token and read_only=true — no auth required"),
    numbered("The access_token is a valid JWT decodable with JWT_SECRET_KEY; sub = demo user's User.id UUID"),
    numbered("GET /api/v1/dashboard with demo token returns 200 (read allowed)"),
    numbered("GET /api/v1/compliance-matrix with demo token returns 200 (read allowed)"),
    numbered("POST /api/v1/ingest with demo token returns 403 with detail containing 'read-only'"),
    numbered("POST /api/v1/hf-processor/run with demo token returns 403 with detail containing 'read-only'"),
    numbered("GET /api/v1/demo/token when SARO_DEMO_TENANT_ID not set returns 503 with clear message"),
    numbered("GET /api/v1/demo/token when demo user does not exist in DB returns 503 with message directing to seed script"),
    numbered("A 5-hour-old demo token returns 401 on any protected endpoint"),
    spacer(),
    h3("Test Cases — tests/test_s205_demo.py (new file)"),
    ...codeBlock(
`# tests/test_s205_demo.py
import pytest
from httpx import AsyncClient
from jose import jwt
import os

# VERIFY: 'client' fixture = unauthenticated AsyncClient
# VERIFY: 'auth_client' fixture = authenticated AsyncClient (super_admin)
# VERIFY: 'demo_user' fixture = User with email demo@saro-platform.io in DB
# VERIFY: 'demo_tenant' fixture = Tenant for the demo user

async def test_demo_token_no_auth_required(client):
    """Public endpoint — no Authorization header needed."""
    resp = await client.get("/api/v1/demo/token")
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["read_only"] is True
    assert data["expires_in_hours"] == 4

async def test_demo_token_sub_is_user_id_not_tenant_id(client, demo_user, demo_tenant):
    """Critical: sub must be user UUID so get_current_user can look up the user."""
    resp  = await client.get("/api/v1/demo/token")
    token = resp.json()["access_token"]
    decoded = jwt.decode(
        token,
        os.getenv("JWT_SECRET_KEY", "test-secret-key-not-for-production"),
        algorithms=[os.getenv("JWT_ALGORITHM", "HS256")],
    )
    assert decoded["sub"] == str(demo_user.id), \\
        "sub must be user UUID, not tenant UUID — get_current_user looks up by User.id"
    assert decoded["read_only"] is True
    assert decoded["tenant_id"] == str(demo_tenant.id)

async def test_demo_token_allows_read_dashboard(client):
    token_resp = await client.get("/api/v1/demo/token")
    token = token_resp.json()["access_token"]
    resp = await client.get(
        "/api/v1/dashboard/kpis",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, \\
        f"Demo token must allow GET /dashboard/kpis, got {resp.status_code}"

async def test_demo_token_blocks_post_ingest(client):
    """Demo token must return 403 on write endpoints."""
    token_resp = await client.get("/api/v1/demo/token")
    token = token_resp.json()["access_token"]
    resp = await client.post(
        "/api/v1/ingest",
        json={"prompt": "Q", "raw_output": "A",
              "source_model": "openai", "tenant_id": "00000000-0000-0000-0000-000000000000"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert "read-only" in resp.json().get("detail", "").lower() or \\
           "read_only" in resp.json().get("detail", "").lower()

async def test_demo_token_blocks_post_hf_processor_run(client):
    token_resp = await client.get("/api/v1/demo/token")
    token = token_resp.json()["access_token"]
    resp = await client.post(
        "/api/v1/hf-processor/run",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403

async def test_demo_token_503_no_env_var(client, monkeypatch):
    monkeypatch.delenv("SARO_DEMO_TENANT_ID", raising=False)
    resp = await client.get("/api/v1/demo/token")
    assert resp.status_code == 503
    assert "seed_demo_tenant" in resp.json()["detail"].lower() or \\
           "not configured" in resp.json()["detail"].lower()

async def test_demo_token_503_no_demo_user_in_db(client, monkeypatch, demo_tenant,
                                                   db_session):
    """If env var is set but user not in DB, 503 with clear message."""
    monkeypatch.setenv("SARO_DEMO_TENANT_ID", str(demo_tenant.id))
    # Remove demo user from DB to simulate missing seed
    from models import User
    db_session.query(User).filter_by(email="demo@saro-platform.io").delete()
    db_session.commit()
    resp = await client.get("/api/v1/demo/token")
    assert resp.status_code == 503
    assert "seed_demo_tenant" in resp.json()["detail"].lower()`
    ),
    pb(),
  ];
}

// ── FIX-004 ───────────────────────────────────────────────────────────────────
function fix004() {
  return [
    h2("FIX-004  |  S-202 — model_version null gate"),
    twoColTable([
      ["Priority", "P1 — High (hard gate contractual requirement)"],
      ["Owner",    "Alex Rivera (ML Lead)"],
      ["Depends",  "None — one-line change in trace_view.py"],
      ["Affects",  "routers/trace_view.py · tests/test_s202_trace.py"],
    ], 1800, 7560),
    spacer(),
    h3("Problem"),
    para("routers/trace_view.py line 81 sets model_version = 'saro-engine-1.0' as a fallback when no EnhancedTrace record exists. The spec requires model_version to be null in this case so the frontend can display 'Not yet available — awaiting ML Lead review'. The hardcoded fallback means the Alex Rivera hard gate (S-202) can never activate — every audit appears ML-reviewed regardless of whether Alex has set the field."),
    spacer(),
    h3("VERIFY — read before coding"),
    twoColTable([
      ["File", "What to confirm", true],
      ["routers/trace_view.py:81",  "model_version = 'saro-engine-1.0' — the hardcoded fallback to remove"],
      ["routers/trace_view.py:118", "Same fallback exists in export_trace_extended — also fix"],
      ["models.py",                 "EnhancedTrace.model_version column type — confirm nullable"],
    ], 3200, 6160),
    spacer(),
    h3("Code Changes"),
    h4("routers/trace_view.py — two changes (get_trace and export_trace_extended)"),
    para("Change 1: get_trace function (around line 81)"),
    ...codeBlock(
`# routers/trace_view.py — in get_trace()

# FROM:
    model_version = "saro-engine-1.0"
    chain_of_thought: list = []
    if enhanced:
        model_version = enhanced.model_version or model_version
        cot = enhanced.chain_of_thought or {}
        chain_of_thought = cot.get("steps", []) if isinstance(cot, dict) else []

# TO:
    model_version = None      # null = Alex Rivera gate not met — frontend shows "awaiting ML Lead review"
    chain_of_thought: list = []
    if enhanced:
        model_version = enhanced.model_version   # stays None if Alex has not set it
        cot = enhanced.chain_of_thought or {}
        chain_of_thought = cot.get("steps", []) if isinstance(cot, dict) else []`
    ),
    spacer(),
    para("Change 2: export_trace_extended function (around line 118)"),
    ...codeBlock(
`# routers/trace_view.py — in export_trace_extended()

# FROM:
    model_version = "saro-engine-1.0"
    chain_of_thought: list = []
    if enhanced:
        model_version = enhanced.model_version or model_version
        ...

# TO:
    model_version = None
    chain_of_thought: list = []
    if enhanced:
        model_version = enhanced.model_version   # None until Alex Rivera sets it
        ...`
    ),
    spacer(),
    h3("Acceptance Criteria"),
    numbered("GET /api/v1/audit/{id}/trace for an audit with no EnhancedTrace returns model_version: null"),
    numbered("GET /api/v1/audit/{id}/trace for an audit with EnhancedTrace where model_version is null returns model_version: null"),
    numbered("GET /api/v1/audit/{id}/trace for an audit with EnhancedTrace where model_version is set returns the real model_version string"),
    numbered("The string 'saro-engine-1.0' does not appear in any trace response — grep confirms removal"),
    numbered("Export endpoint mirrors the same null behaviour for model_version"),
    numbered("Existing passing S-202 tests continue to pass"),
    spacer(),
    h3("Test Cases — tests/test_s202_trace.py (update existing file)"),
    ...codeBlock(
`# tests/test_s202_trace.py — add these tests to the existing file

import pytest
from models import Audit, AuditTrace, EnhancedTrace

# VERIFY: completed_audit fixture = Audit with status='completed', has AuditTrace rows
# VERIFY: db_session, auth_client fixtures from conftest

async def test_model_version_null_when_no_enhanced_trace(auth_client, db_session,
                                                           completed_audit):
    """Core S-202 gate: model_version must be null before Alex Rivera sets it."""
    # Ensure no EnhancedTrace exists for this audit
    db_session.query(EnhancedTrace).filter_by(audit_id=completed_audit.id).delete()
    db_session.commit()

    resp = await auth_client.get(f"/api/v1/audit/{completed_audit.id}/trace")
    assert resp.status_code == 200
    data = resp.json()
    assert data["model_version"] is None, \\
        "model_version must be null when EnhancedTrace does not exist — " \\
        "found hardcoded 'saro-engine-1.0' fallback"

async def test_model_version_null_when_enhanced_trace_unset(auth_client, db_session,
                                                              completed_audit):
    """model_version stays null even when EnhancedTrace row exists but field is unset."""
    et = EnhancedTrace(
        audit_id=completed_audit.id,
        model_version=None,   # Alex Rivera has NOT reviewed yet
        chain_of_thought={"steps": []},
        export_hash=None,
    )
    db_session.add(et)
    db_session.commit()

    resp = await auth_client.get(f"/api/v1/audit/{completed_audit.id}/trace")
    assert resp.status_code == 200
    assert resp.json()["model_version"] is None

async def test_model_version_populated_when_alex_sets_it(auth_client, db_session,
                                                           completed_audit):
    """model_version is returned when Alex Rivera has set it."""
    et = EnhancedTrace(
        audit_id=completed_audit.id,
        model_version="saro-engine-2.1-healthcare",
        chain_of_thought={"steps": [
            {"step": 1, "gate_name": "Data Quality",        "result": "pass", "reason": "ok", "regulation_ref": "NIST-MAP-1.1"},
            {"step": 2, "gate_name": "Fairness",            "result": "pass", "reason": "ok", "regulation_ref": "NIST-MEASURE-2.5"},
            {"step": 3, "gate_name": "Risk Classification", "result": "warn", "reason": "moderate risk", "regulation_ref": "EU-AI-ACT-9"},
            {"step": 4, "gate_name": "Compliance Mapping",  "result": "pass", "reason": "ok", "regulation_ref": "NIST-MANAGE-1.3"},
        ]},
        export_hash="abc123",
    )
    db_session.add(et)
    db_session.commit()

    resp = await auth_client.get(f"/api/v1/audit/{completed_audit.id}/trace")
    assert resp.status_code == 200
    data = resp.json()
    assert data["model_version"] == "saro-engine-2.1-healthcare"
    assert len(data["chain_of_thought"]) == 4

async def test_hardcoded_fallback_string_not_in_response(auth_client, db_session,
                                                          completed_audit):
    """Regression guard: 'saro-engine-1.0' must never appear in a response."""
    db_session.query(EnhancedTrace).filter_by(audit_id=completed_audit.id).delete()
    db_session.commit()
    resp = await auth_client.get(f"/api/v1/audit/{completed_audit.id}/trace")
    assert "saro-engine-1.0" not in resp.text

async def test_cross_tenant_trace_returns_404(auth_client, db_session,
                                               other_tenant_audit):
    """S-202 security: cross-tenant trace access must return 404, not 200."""
    # VERIFY: other_tenant_audit fixture = completed Audit belonging to a DIFFERENT tenant
    resp = await auth_client.get(f"/api/v1/audit/{other_tenant_audit.id}/trace")
    assert resp.status_code == 404, \\
        "Cross-tenant trace access must return 404 — no data leakage"

async def test_export_model_version_matches_trace_response(auth_client, db_session,
                                                            completed_audit):
    """Export endpoint must return the same model_version as the trace endpoint."""
    db_session.query(EnhancedTrace).filter_by(audit_id=completed_audit.id).delete()
    db_session.commit()
    trace_resp  = await auth_client.get(f"/api/v1/audit/{completed_audit.id}/trace")
    export_resp = await auth_client.get(f"/api/v1/audit/{completed_audit.id}/trace/export")
    assert export_resp.status_code == 200
    assert trace_resp.json()["model_version"] == export_resp.json().get("model_version")`
    ),
    pb(),
  ];
}

// ── FIX-005 ───────────────────────────────────────────────────────────────────
function fix005() {
  return [
    h2("FIX-005  |  S-201 — React/Vite Dashboard Frontend"),
    twoColTable([
      ["Priority", "P1 — High (required for client demos)"],
      ["Owner",    "Venky"],
      ["Depends",  "FIX-001 (correct API URLs), FIX-003 (working demo token), S-000 (demo data)"],
      ["Affects",  "frontend/react/ (new directory alongside existing Streamlit)"],
    ], 1800, 7560),
    spacer(),
    h3("Problem"),
    para("No React/Vite frontend exists. The production app serves Streamlit from frontend/app.py. Spec S-201 requires a React dashboard connected to real API endpoints. Spec S-205 requires a /demo route with auto-authentication. Neither exists."),
    spacer(),
    h3("Scope and Integration Rule"),
    para("The React app is created in frontend/react/ alongside the existing Streamlit app. Do NOT delete or modify the Streamlit app — it may still be in use. The React app is served as a new Fly.io / Railway service (separate port) OR as FastAPI StaticFiles mount. VERIFY with Venky which serving approach to use before starting."),
    spacer(),
    h3("VERIFY — read before coding"),
    twoColTable([
      ["File / Question", "What to confirm", true],
      ["main.py",         "Does FastAPI currently serve any static files? Check for StaticFiles mounts"],
      ["Dockerfile",      "Is there a build step for a frontend? Check for node/npm in Dockerfile"],
      ["fly.toml [[statics]]", "Is [[statics]] section commented or absent? Determines how to serve React build"],
      ["Venky decision",  "Should React be served from FastAPI (StaticFiles) or a separate service? This affects the Dockerfile and fly.toml."],
      ["routers/dashboard.py:4-5", "Confirm exact API paths: /api/v1/dashboard/kpis and /api/v1/dashboard/audits"],
      ["routers/compliance_matrix.py", "Confirm /api/v1/compliance-matrix/coverage endpoint exists and response shape"],
      ["routers/risk_dashboard.py", "Confirm /api/v1/risk-dashboard endpoint and response shape"],
    ], 3400, 5960),
    spacer(),
    h3("File Structure to Create"),
    ...codeBlock(
`frontend/react/
├── package.json               (Vite + React + TypeScript)
├── vite.config.ts             (proxy /api/* to FastAPI on dev)
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx                (router: /, /demo, /demo/*)
│   ├── api/
│   │   └── saro.ts            (centralised API client — all fetch calls here)
│   ├── hooks/
│   │   ├── useAuth.ts         (token storage, auto-refresh)
│   │   └── usePresentationMode.ts
│   ├── pages/
│   │   ├── Dashboard.tsx      (S-201 main view)
│   │   └── DemoEntry.tsx      (S-205 auto-auth entry point)
│   └── components/
│       ├── FlowStrip.tsx      (S-201 5-node pipeline animation)
│       ├── LiveFeed.tsx        (S-201 audit list, auto-refresh)
│       ├── MetricsRow.tsx      (S-201 KPI cards)
│       ├── RegCoverage.tsx     (S-203 compliance heatmap)
│       └── EngineScores.tsx    (S-201 risk score gauges)`
    ),
    spacer(),
    h3("Key File Specifications"),
    h4("src/api/saro.ts — centralised API client"),
    ...codeBlock(
`// frontend/react/src/api/saro.ts
// Single source of truth for all SARO API calls.
// No fetch() calls allowed outside this file.

const BASE = import.meta.env.VITE_API_URL ?? "";

function getToken(): string {
  return (
    sessionStorage.getItem("saro_demo_token") ??
    sessionStorage.getItem("saro_token") ??
    localStorage.getItem("saro_token") ??
    ""
  );
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const resp = await fetch(BASE + path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: \`Bearer \${token}\` } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw Object.assign(new Error(body), { status: resp.status });
  }
  return resp.json() as Promise<T>;
}

// Dashboard
export const getDashboardKPIs    = () => apiFetch("/api/v1/dashboard/kpis");
export const getDashboardAudits  = (params = "") =>
  apiFetch(\`/api/v1/dashboard/audits\${params}\`);

// Compliance matrix
export const getComplianceCoverage = () =>
  apiFetch("/api/v1/compliance-matrix/coverage");

// HF Processor
export const getHFQueueStatus = () =>
  apiFetch("/api/v1/hf-processor/status");

// Demo
export const getDemoToken = () => apiFetch<{
  access_token: string; read_only: boolean; expires_in_hours: number;
}>("/api/v1/demo/token");`
    ),
    spacer(),
    h4("src/pages/DemoEntry.tsx — S-205 auto-auth entry point"),
    ...codeBlock(
`// frontend/react/src/pages/DemoEntry.tsx
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getDemoToken } from "../api/saro";

export default function DemoEntry() {
  const navigate = useNavigate();
  const [params]  = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDemoToken()
      .then((data) => {
        // NEVER localStorage — demo token must not persist across sessions
        sessionStorage.setItem("saro_demo_token", data.access_token);
        sessionStorage.setItem("saro_demo_mode", "true");
        const view = params.get("view") ?? "dashboard";
        const mode = params.get("mode") ?? "";
        navigate(\`/demo/\${view}\${mode ? "?mode=" + mode : ""}\`, { replace: true });
      })
      .catch((err) => setError(err.message));
  }, []);

  if (error)
    return (
      <div style={{ padding: 32 }}>
        <h2>Demo not available</h2>
        <p>{error}</p>
        <p>Run: python scripts/seed_demo_tenant.py to initialise the demo tenant.</p>
      </div>
    );

  return (
    <div style={{ display:"flex", alignItems:"center",
                  justifyContent:"center", height:"100vh" }}>
      <p>Loading SARO demo...</p>
    </div>
  );
}`
    ),
    spacer(),
    h4("src/hooks/usePresentationMode.ts"),
    ...codeBlock(
`// frontend/react/src/hooks/usePresentationMode.ts
import { useSearchParams } from "react-router-dom";
export function usePresentationMode(): boolean {
  const [params] = useSearchParams();
  return params.get("mode") === "presentation";
}`
    ),
    spacer(),
    h4("src/components/FlowStrip.tsx — pipeline animation"),
    ...codeBlock(
`// frontend/react/src/components/FlowStrip.tsx
// 5-node strip: AI Vendor -> /ingest -> Engine -> TRACE -> Risk Score
// Polls GET /api/v1/dashboard/audits?limit=1&sort=desc every 3s.
// When most-recent audit status changes running->completed, animates nodes in sequence.
// In presentation mode, step delay = 800ms. Normal = 300ms.

import { useEffect, useState, useRef } from "react";
import { usePresentationMode } from "../hooks/usePresentationMode";
import { getDashboardAudits } from "../api/saro";

const NODES = [
  { id: "vendor",  label: "AI Vendor",    sub: "openai / claude / grok" },
  { id: "ingest",  label: "/ingest",       sub: "FastAPI POST" },
  { id: "engine",  label: "Engine Router", sub: "4-gate pipeline" },
  { id: "trace",   label: "TRACE",         sub: "Evidence log" },
  { id: "score",   label: "Risk Score",    sub: "MIT coverage" },
];

type NodeState = "idle" | "active" | "done";

export default function FlowStrip() {
  const [states, setStates] = useState<NodeState[]>(NODES.map(() => "idle"));
  const isPresentation = usePresentationMode();
  const stepDelay = isPresentation ? 800 : 300;
  const lastAuditStatus = useRef<string | null>(null);

  useEffect(() => {
    const poll = setInterval(async () => {
      try {
        const data: any = await getDashboardAudits("?limit=1&sort=desc");
        const latest = (data.items ?? data)[0];
        if (!latest) return;
        if (latest.status === "running" && lastAuditStatus.current !== "running") {
          setStates(["active", "idle", "idle", "idle", "idle"]);
        }
        if (latest.status === "completed" && lastAuditStatus.current !== "completed") {
          // Animate each node completing in sequence
          NODES.forEach((_, i) => {
            setTimeout(() => {
              setStates(prev => prev.map((s, j) =>
                j < i     ? "done"   :
                j === i   ? "active" : "idle"
              ));
              if (i === NODES.length - 1)
                setStates(NODES.map(() => "done"));
            }, i * stepDelay);
          });
        }
        lastAuditStatus.current = latest.status;
      } catch (_) {}
    }, 3000);
    return () => clearInterval(poll);
  }, [stepDelay]);

  return (
    <div style={{ display:"flex", gap:8, padding:"16px 0" }}>
      {NODES.map((node, i) => (
        <div key={node.id} style={{
          flex: 1, textAlign:"center", padding:12, borderRadius:8,
          background: states[i]==="done" ? "#0D7A75" :
                      states[i]==="active" ? "#7DD3D0" : "#F3F4F6",
          color: states[i]==="idle" ? "#374151" : "#FFFFFF",
          transition: "background 0.3s",
        }}>
          <div style={{ fontWeight:700 }}>{node.label}</div>
          <div style={{ fontSize:12, opacity:0.8 }}>{node.sub}</div>
        </div>
      ))}
    </div>
  );
}`
    ),
    spacer(),
    h4("package.json"),
    ...codeBlock(
`{
  "name": "saro-frontend",
  "version": "1.0.0",
  "scripts": {
    "dev":     "vite",
    "build":   "tsc && vite build",
    "preview": "vite preview",
    "test":    "vitest run"
  },
  "dependencies": {
    "react":            "^18.3.0",
    "react-dom":        "^18.3.0",
    "react-router-dom": "^6.25.0"
  },
  "devDependencies": {
    "@types/react":             "^18.3.0",
    "@types/react-dom":         "^18.3.0",
    "@vitejs/plugin-react":     "^4.3.0",
    "typescript":               "^5.5.0",
    "vite":                     "^5.4.0",
    "vitest":                   "^2.0.0",
    "@testing-library/react":   "^16.0.0",
    "@testing-library/jest-dom":"^6.0.0",
    "playwright":               "^1.46.0"
  }
}`
    ),
    spacer(),
    h4("vite.config.ts"),
    ...codeBlock(
`import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
  },
});`
    ),
    spacer(),
    h3("Dockerfile addition — serve React build from FastAPI"),
    para("Add to Dockerfile AFTER the Python dependency install step:"),
    ...codeBlock(
`# Dockerfile — add React build step
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend/react
COPY frontend/react/package*.json ./
RUN npm ci
COPY frontend/react/ ./
RUN npm run build
# dist/ output is at /app/frontend/react/dist

# In the Python stage, copy the built assets:
COPY --from=frontend-build /app/frontend/react/dist /app/frontend/react/dist`
    ),
    spacer(),
    para("Add to main.py to serve the React build (append after all router registrations):"),
    ...codeBlock(
`# main.py — ADD at end of file, after all app.include_router() calls
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_REACT_DIST = os.path.join(os.path.dirname(__file__), "frontend", "react", "dist")

if os.path.isdir(_REACT_DIST):
    # Serve React static assets
    app.mount("/assets", StaticFiles(directory=os.path.join(_REACT_DIST, "assets")), name="react-assets")

    @app.get("/demo/{path:path}", include_in_schema=False)
    @app.get("/dashboard", include_in_schema=False)
    @app.get("/", include_in_schema=False)
    async def serve_react(path: str = ""):
        index = os.path.join(_REACT_DIST, "index.html")
        return FileResponse(index)
else:
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "React build not found at %s — run 'npm run build' in frontend/react/", _REACT_DIST
    )`
    ),
    spacer(),
    h3("Acceptance Criteria"),
    numbered("npm run build in frontend/react/ completes without error"),
    numbered("GET / in browser loads the React app, not Streamlit"),
    numbered("GET /demo auto-authenticates as demo tenant and redirects to /demo/dashboard within 5 seconds"),
    numbered("Dashboard shows live data: KPI cards, audit live feed, compliance heatmap"),
    numbered("KPI card values match direct API call to GET /api/v1/dashboard/kpis — no discrepancy"),
    numbered("GET /demo?mode=presentation hides: tenant switcher, HF processor panel"),
    numbered("GET /demo?mode=presentation shows: FlowStrip, metrics, live feed, compliance heatmap"),
    numbered("FlowStrip animation uses 800ms step delay in presentation mode, 300ms in normal mode"),
    numbered("Dashboard blank state shows a message, not an error, when no audits exist"),
    numbered("API 503 response shows a degraded banner — dashboard does not crash"),
    numbered("No hardcoded data in any component — all values fetched from /api/v1/* endpoints"),
    spacer(),
    h3("Test Cases — tests/test_s201_dashboard.py (update) and tests/e2e/test_demo_ui.py (new)"),
    ...codeBlock(
`# tests/test_s201_dashboard.py — add API contract tests

async def test_kpis_returns_numeric_fields_on_empty_tenant(auth_client):
    """Dashboard KPIs must return valid numeric fields even with 0 audits."""
    resp = await auth_client.get("/api/v1/dashboard/kpis")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data.get("total_audits", 0), int)
    # avg_risk_score may be null with 0 audits — that is acceptable
    if data.get("avg_risk_score") is not None:
        assert isinstance(data["avg_risk_score"], float)

async def test_audits_list_is_sortable(auth_client):
    """Dashboard audit list must accept sort parameters."""
    resp = await auth_client.get("/api/v1/dashboard/audits?sort_by=created_at&sort_dir=desc")
    assert resp.status_code == 200

async def test_compliance_coverage_returns_frameworks(auth_client):
    resp = await auth_client.get("/api/v1/compliance-matrix/coverage")
    assert resp.status_code == 200
    data = resp.json()
    assert "frameworks" in data
    assert isinstance(data["frameworks"], list)

async def test_hf_processor_status_accessible(auth_client):
    resp = await auth_client.get("/api/v1/hf-processor/status")
    assert resp.status_code == 200`
    ),
    spacer(),
    ...codeBlock(
`# tests/e2e/test_demo_ui.py — Playwright E2E tests
# Run: playwright test tests/e2e/ --base-url https://saro-api.fly.dev
# VERIFY: PLAYWRIGHT_BASE_URL env var set in CI

import pytest
from playwright.sync_api import Page, expect

BASE = "https://saro-api.fly.dev"   # VERIFY: update to production URL

def test_demo_redirects_to_dashboard(page: Page):
    """GET /demo must redirect to /demo/dashboard within 5 seconds."""
    page.goto(f"{BASE}/demo", wait_until="networkidle")
    expect(page).to_have_url(f"{BASE}/demo/dashboard", timeout=5000)

def test_presentation_mode_hides_admin_panels(page: Page):
    page.goto(f"{BASE}/demo?mode=presentation", wait_until="networkidle")
    # Tenant switcher must not be visible
    expect(page.locator("[data-testid='tenant-switcher']")).not_to_be_visible()
    # HF processor panel must not be visible
    expect(page.locator("[data-testid='hf-processor-panel']")).not_to_be_visible()

def test_presentation_mode_shows_flow_strip(page: Page):
    page.goto(f"{BASE}/demo?mode=presentation", wait_until="networkidle")
    expect(page.locator("[data-testid='flow-strip']")).to_be_visible()

def test_dashboard_shows_audit_rows(page: Page):
    """Dashboard live feed must show at least 1 row from seed data."""
    page.goto(f"{BASE}/demo/dashboard", wait_until="networkidle")
    rows = page.locator("[data-testid='audit-row']")
    expect(rows.first).to_be_visible(timeout=8000)

def test_kpi_cards_not_hardcoded(page: Page):
    """KPI values must not be static — they must come from the API."""
    page.goto(f"{BASE}/demo/dashboard", wait_until="networkidle")
    # If KPI card shows a value, it must be numeric (not placeholder text)
    kpi = page.locator("[data-testid='kpi-total-audits']")
    expect(kpi).to_be_visible()
    text = kpi.inner_text()
    assert text.isdigit() or text.replace(",", "").isdigit(), \\
        f"KPI total_audits shows non-numeric value: '{text}'"

def test_flow_strip_has_five_nodes(page: Page):
    page.goto(f"{BASE}/demo/dashboard", wait_until="networkidle")
    nodes = page.locator("[data-testid='flow-node']")
    expect(nodes).to_have_count(5)`
    ),
    pb(),
  ];
}

// ── Section 4: Contract Compliance Tests ─────────────────────────────────────
function contractTests() {
  return [
    h1("Section 4 — Contract Compliance Tests"),
    para("These test files verify the SPEC CONTRACT, not just the current implementation. They are separate from the fix-specific tests above. Each file targets a story marked Partial or Fail in the audit. Run these tests to confirm a story is truly done."),
    spacer(),
    h2("S-000 — Demo Seed Script Contract Tests"),
    h3("tests/test_s000_seed.py (new file)"),
    ...codeBlock(
`# tests/test_s000_seed.py
import pytest, os

def test_env_demo_gitignored():
    """S-000 acceptance criteria #5: .env.demo must be in .gitignore."""
    with open(".gitignore") as f:
        content = f.read()
    assert ".env.demo" in content, \\
        ".env.demo must be in .gitignore — it contains demo credentials"

def test_seed_script_exists():
    assert os.path.exists("scripts/seed_demo_tenant.py")

def test_seed_script_is_idempotent(db_session):
    """Running seed twice must not create two tenants."""
    from scripts.seed_demo_tenant import get_or_create_demo_tenant
    r1 = get_or_create_demo_tenant(db_session)
    r2 = get_or_create_demo_tenant(db_session)
    assert r1["tenant_id"] == r2["tenant_id"]
    assert r2["created"] is False

def test_env_demo_written(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from scripts.seed_demo_tenant import write_env_demo
    write_env_demo("test-tenant-id", "test-token", "https://saro-api.fly.dev")
    content = (tmp_path / ".env.demo").read_text()
    assert "SARO_DEMO_TENANT_ID=test-tenant-id" in content
    assert "SARO_DEMO_TOKEN=test-token" in content
    assert "SARO_DEMO_URL=https://saro-api.fly.dev" in content`
    ),
    spacer(),
    h2("S-002 — HF Sampler Contract Tests"),
    h3("tests/test_s002_contract.py (new file)"),
    ...codeBlock(
`# tests/test_s002_contract.py
import pytest, argparse

def test_hf_sampler_accepts_count_arg():
    """Spec says --count; CI workflow passes --count. Must not require --samples."""
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "scripts/hf_sampler.py", "--help"],
        capture_output=True, text=True,
    )
    combined = result.stdout + result.stderr
    assert "--count" in combined, \\
        "hf_sampler.py must accept --count argument (spec and CI workflow use --count)"
    # --samples must NOT be the only accepted form
    # Either both work (alias) or only --count works

def test_finance_dataset_uses_instruction_field(monkeypatch):
    """Spec requires instruction field for finance dataset."""
    from scripts.hf_sampler import DATASET_REGISTRY
    finance = DATASET_REGISTRY.get("finance", {})
    # VERIFY: confirm field name — spec says 'instruction' for gbharti/finance-alpaca
    # If the implementation uses 'input', update this test to match the confirmed field
    assert finance.get("prompt_field") in ("instruction", "input"), \\
        f"Finance prompt field must be instruction or input, got: {finance.get('prompt_field')}"

def test_all_four_verticals_registered():
    from scripts.hf_sampler import DATASET_REGISTRY
    for v in ["finance", "healthcare", "technology", "government"]:
        assert v in DATASET_REGISTRY, f"Vertical '{v}' missing from DATASET_REGISTRY"

def test_count_zero_inserts_nothing(monkeypatch, db_session, demo_tenant):
    from unittest.mock import patch
    mock_rows = [{"instruction": f"Q{i}", "output": f"A{i}"} for i in range(5)]
    with patch("scripts.hf_sampler.load_dataset", return_value=iter(mock_rows)):
        from scripts.hf_sampler import stream_rows
        rows = list(stream_rows("finance", 0))
    assert len(rows) == 0`
    ),
    spacer(),
    h2("S-101 — Ingest Endpoint Contract Tests"),
    h3("tests/test_s101_contract.py (new file)"),
    ...codeBlock(
`# tests/test_s101_contract.py
# Tests spec S-101 acceptance criteria against the actual implementation.
# NOTE: The implementation uses 'prompt' and 'raw_output' field names.
# The original spec said 'prompt_text' and 'raw_output_text'.
# These tests verify the IMPLEMENTATION'S contract (what the code actually accepts).

import pytest
from httpx import AsyncClient
from models import Audit, AuditMetadata

VALID_PAYLOAD = {
    "prompt":       "What is the credit risk for this applicant?",
    "raw_output":   "Based on DTI ratio of 0.45, risk is moderate.",
    "source_model": "openai",
    "vertical":     "finance",
    "tenant_id":    None,   # filled by conftest using demo_tenant fixture
}

async def test_valid_ingest_returns_201(auth_client, demo_tenant, valid_ingest_payload):
    resp = await auth_client.post("/api/v1/ingest", json=valid_ingest_payload)
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "audit_id" in data
    assert data["status"] == "running"
    assert "trace_url" in data

async def test_audit_row_created_with_running_status(auth_client, db_session,
                                                      demo_tenant, valid_ingest_payload):
    resp = await auth_client.post("/api/v1/ingest", json=valid_ingest_payload)
    assert resp.status_code == 201
    audit_id = resp.json()["audit_id"]
    audit = db_session.query(Audit).filter_by(id=audit_id).first()
    assert audit is not None
    assert audit.status == "running"

async def test_audit_metadata_created(auth_client, db_session,
                                       demo_tenant, valid_ingest_payload):
    resp = await auth_client.post("/api/v1/ingest", json=valid_ingest_payload)
    audit_id = resp.json()["audit_id"]
    meta = db_session.query(AuditMetadata).filter_by(audit_id=audit_id).first()
    assert meta is not None
    assert meta.source_model == "openai"
    assert meta.ingestion_method == "api"

async def test_invalid_source_model_returns_422(auth_client, demo_tenant,
                                                  valid_ingest_payload):
    bad = {**valid_ingest_payload, "source_model": "not_a_vendor"}
    resp = await auth_client.post("/api/v1/ingest", json=bad)
    assert resp.status_code == 422

async def test_empty_prompt_returns_422(auth_client, demo_tenant, valid_ingest_payload):
    bad = {**valid_ingest_payload, "prompt": ""}
    resp = await auth_client.post("/api/v1/ingest", json=bad)
    assert resp.status_code == 422

async def test_wrong_tenant_returns_403(auth_client, other_tenant, valid_ingest_payload):
    bad = {**valid_ingest_payload, "tenant_id": str(other_tenant.id)}
    resp = await auth_client.post("/api/v1/ingest", json=bad)
    assert resp.status_code == 403

async def test_no_auth_returns_401(client, valid_ingest_payload):
    resp = await client.post("/api/v1/ingest", json=valid_ingest_payload)
    assert resp.status_code == 401

async def test_response_within_500ms(auth_client, demo_tenant, valid_ingest_payload):
    import time
    start = time.monotonic()
    await auth_client.post("/api/v1/ingest", json=valid_ingest_payload)
    assert (time.monotonic() - start) < 0.5, "POST /ingest must return within 500ms"`
    ),
    spacer(),
    h2("S-103 — SDK Snippet Contract Tests"),
    h3("tests/test_s103_contract.py (new file)"),
    ...codeBlock(
`# tests/test_s103_contract.py

import pytest

async def test_python_snippet_returns_200(auth_client):
    resp = await auth_client.get("/api/v1/sdk/snippet?lang=python")
    assert resp.status_code == 200

async def test_javascript_snippet_returns_200(auth_client):
    """S-103 requires lang=javascript support."""
    resp = await auth_client.get("/api/v1/sdk/snippet?lang=javascript")
    assert resp.status_code == 200, \\
        "lang=javascript must be supported (currently only Python is implemented)"

async def test_curl_snippet_returns_200(auth_client):
    """S-103 requires lang=curl support."""
    resp = await auth_client.get("/api/v1/sdk/snippet?lang=curl")
    assert resp.status_code == 200, \\
        "lang=curl must be supported"

async def test_invalid_lang_returns_400(auth_client):
    resp = await auth_client.get("/api/v1/sdk/snippet?lang=ruby")
    assert resp.status_code == 400, \\
        "Unsupported lang must return 400, not 200 or 422"

async def test_snippet_contains_tenant_id(auth_client, demo_tenant):
    resp = await auth_client.get("/api/v1/sdk/snippet?lang=python")
    assert resp.status_code == 200
    # The caller's tenant_id must appear in the snippet
    body = resp.json() if resp.headers.get("content-type","").startswith("application/json") \\
           else {"snippet": resp.text}
    snippet = body.get("snippet", resp.text)
    assert str(demo_tenant.id) in snippet, \\
        "Snippet must contain the caller's tenant_id pre-filled"`
    ),
    spacer(),
    h2("S-203 — Compliance Coverage Contract Tests"),
    h3("tests/test_s203_contract.py (new file)"),
    ...codeBlock(
`# tests/test_s203_contract.py

import pytest

async def test_coverage_endpoint_accessible(auth_client):
    """Coverage must be at /api/v1/compliance-matrix/coverage (hyphen, not underscore)."""
    resp = await auth_client.get("/api/v1/compliance-matrix/coverage")
    assert resp.status_code == 200, \\
        f"Coverage endpoint returned {resp.status_code} — check URL (hyphen vs underscore)"

async def test_coverage_returns_frameworks_list(auth_client):
    resp = await auth_client.get("/api/v1/compliance-matrix/coverage")
    data = resp.json()
    assert "frameworks" in data
    for fw in data["frameworks"]:
        assert "framework"    in fw
        assert "total_rules"  in fw
        assert "coverage_pct" in fw
        assert isinstance(fw["coverage_pct"], float)

async def test_coverage_pct_is_zero_when_no_audits(auth_client, empty_tenant_client):
    """Tenant with 0 audits: all coverage_pct values must be 0.0."""
    # VERIFY: empty_tenant_client fixture = auth client for a tenant with no audits
    resp = await empty_tenant_client.get("/api/v1/compliance-matrix/coverage")
    assert resp.status_code == 200
    for fw in resp.json()["frameworks"]:
        assert fw["coverage_pct"] == 0.0, \\
            f"Framework {fw['framework']} shows {fw['coverage_pct']}% with no audits"

async def test_unauthenticated_returns_401(client):
    resp = await client.get("/api/v1/compliance-matrix/coverage")
    assert resp.status_code == 401`
    ),
    spacer(),
    h2("S-204 — Remediation Contract Tests"),
    h3("tests/test_s204_contract.py (new file)"),
    ...codeBlock(
`# tests/test_s204_contract.py

import pytest, uuid

async def test_list_open_traces(auth_client):
    """GET /api/v1/remediation must return open fail/warn traces."""
    resp = await auth_client.get("/api/v1/remediation")
    assert resp.status_code == 200
    data = resp.json()
    assert "traces" in data or "items" in data
    assert "total" in data

async def test_remediate_trace_patch(auth_client, db_session, demo_tenant,
                                      failing_audit_trace):
    """PATCH mark-remediated must set is_remediated=true, remediated_by_id."""
    trace_id = str(failing_audit_trace.id)
    resp = await auth_client.patch(
        f"/api/v1/remediation/traces/{trace_id}/remediate",
        json={"remediation_note": "Fixed by updating training data"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_remediated"] is True
    assert data["remediated_by_id"] is not None

async def test_remediated_trace_removed_from_open_list(auth_client, db_session,
                                                         failing_audit_trace):
    trace_id = str(failing_audit_trace.id)
    await auth_client.patch(
        f"/api/v1/remediation/traces/{trace_id}/remediate",
        json={"remediation_note": "resolved"},
    )
    resp = await auth_client.get("/api/v1/remediation")
    trace_ids = [t["id"] for t in (resp.json().get("traces") or resp.json().get("items", []))]
    assert trace_id not in trace_ids, \\
        "Remediated trace must not appear in open list"

async def test_bulk_remediate_endpoint(auth_client, db_session, demo_tenant):
    """POST /api/v1/remediation/bulk-remediate must accept list of trace IDs."""
    resp = await auth_client.post(
        "/api/v1/remediation/bulk-remediate",
        json={"trace_ids": [], "remediation_note": "bulk"},
    )
    assert resp.status_code in (200, 422), \\
        "Bulk remediate endpoint must exist (200 for valid, 422 for empty list)"

async def test_cross_tenant_trace_access_denied(auth_client, other_tenant_trace):
    """Cannot remediate a trace belonging to a different tenant."""
    resp = await auth_client.patch(
        f"/api/v1/remediation/traces/{other_tenant_trace.id}/remediate",
        json={"remediation_note": "should fail"},
    )
    assert resp.status_code in (403, 404)`
    ),
    spacer(),
    h2("S-302 — CI/CD Contract Tests"),
    h3("tests/test_s302_cicd.py (new file)"),
    ...codeBlock(
`# tests/test_s302_cicd.py
# Validates .github/workflows/deploy.yml structure without running CI.

import pytest, yaml, os

DEPLOY_YML = ".github/workflows/deploy.yml"

def load_workflow():
    with open(DEPLOY_YML) as f:
        return yaml.safe_load(f)

def test_deploy_workflow_exists():
    assert os.path.exists(DEPLOY_YML)

def test_test_job_exists():
    wf = load_workflow()
    assert "test" in wf["jobs"], "CI must have a 'test' job"

def test_deploy_needs_test():
    wf = load_workflow()
    deploy = wf["jobs"].get("deploy", {})
    needs = deploy.get("needs", [])
    if isinstance(needs, str): needs = [needs]
    assert "test" in needs, "deploy job must depend on test job"

def test_health_check_needs_deploy():
    wf = load_workflow()
    hc = wf["jobs"].get("health-check", {})
    needs = hc.get("needs", [])
    if isinstance(needs, str): needs = [needs]
    assert "deploy" in needs

def test_ruff_lint_step_present():
    wf = load_workflow()
    test_steps = wf["jobs"]["test"]["steps"]
    step_names = [s.get("name", "").lower() for s in test_steps]
    assert any("ruff" in n or "lint" in n for n in step_names), \\
        "Ruff lint step must be present in test job"

def test_pytest_step_present():
    wf = load_workflow()
    test_steps = wf["jobs"]["test"]["steps"]
    runs = " ".join(s.get("run", "") for s in test_steps if "run" in s)
    assert "pytest" in runs, "pytest must be called in the test job"

def test_health_check_url_matches_fly_toml_app_name():
    """CI health-check URL must match the app name in fly.toml."""
    import re
    with open("fly.toml") as f:
        fly = f.read()
    app_match = re.search(r'app\\s*=\\s*"([^"]+)"', fly)
    assert app_match, "Cannot find app name in fly.toml"
    app_name = app_match.group(1)

    wf = load_workflow()
    hc_steps = wf["jobs"].get("health-check", {}).get("steps", [])
    hc_script = " ".join(s.get("run", "") for s in hc_steps)
    expected_fragment = f"{app_name}.fly.dev/health"
    assert expected_fragment in hc_script, \\
        f"Health-check must ping {expected_fragment} — app name mismatch between fly.toml and deploy.yml"`
    ),
    pb(),
  ];
}

// ── Section 5: Files Changed Checklist ───────────────────────────────────────
function filesChecklist() {
  return [
    h1("Section 5 — Master Files Checklist"),
    para("Execution order: apply fixes in this sequence to avoid dependency issues."),
    spacer(),
    new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: [1000, 4000, 2000, 2360],
      rows: [
        new TableRow({ tableHeader: true, children: [
          headerCell("Order", 1000), headerCell("File", 4000),
          headerCell("Fix", 2000), headerCell("Action", 2360),
        ]}),
        new TableRow({ children: [
          dataCell("1", C.white, true, 1000), dataCell("routers/hf_processor.py", C.white, false, 4000),
          dataCell("FIX-001", C.yellowBg, true, 2000), dataCell("EDIT — rename prefix + endpoints", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("2", C.white, true, 1000), dataCell("fly.toml", C.white, false, 4000),
          dataCell("FIX-002", C.yellowBg, true, 2000), dataCell("EDIT — auto_stop_machines + health check", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("3", C.white, true, 1000), dataCell(".github/workflows/deploy.yml", C.white, false, 4000),
          dataCell("FIX-002", C.yellowBg, true, 2000), dataCell("EDIT — fix health-check URL", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("4", C.white, true, 1000), dataCell("auth.py", C.white, false, 4000),
          dataCell("FIX-003", C.redBg, true, 2000), dataCell("EDIT — attach read_only claim to user", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("5", C.white, true, 1000), dataCell("routers/demo.py", C.white, false, 4000),
          dataCell("FIX-003", C.redBg, true, 2000), dataCell("EDIT — fix get_demo_token JWT sub", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("6", C.white, true, 1000), dataCell("routers/ingest.py", C.white, false, 4000),
          dataCell("FIX-003", C.redBg, true, 2000), dataCell("EDIT — add require_write_access dependency", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("7", C.white, true, 1000), dataCell("routers/trace_view.py", C.white, false, 4000),
          dataCell("FIX-004", C.yellowBg, true, 2000), dataCell("EDIT — model_version fallback = None (2 sites)", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("8", C.white, true, 1000), dataCell("frontend/react/ (entire directory)", C.white, false, 4000),
          dataCell("FIX-005", C.blueBg, true, 2000), dataCell("CREATE — new React/Vite project", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("9", C.white, true, 1000), dataCell("Dockerfile", C.white, false, 4000),
          dataCell("FIX-005", C.blueBg, true, 2000), dataCell("EDIT — add frontend build stage", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("10", C.white, true, 1000), dataCell("main.py", C.white, false, 4000),
          dataCell("FIX-005", C.blueBg, true, 2000), dataCell("EDIT — mount StaticFiles for React build", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("11", C.white, true, 1000), dataCell("tests/test_s003_hf_processor.py", C.white, false, 4000),
          dataCell("FIX-001", C.yellowBg, true, 2000), dataCell("EDIT — update endpoint URLs in tests", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("12", C.white, true, 1000), dataCell("tests/test_s000_seed.py", C.white, false, 4000),
          dataCell("Contract", C.greenBg, true, 2000), dataCell("CREATE — new test file", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("13", C.white, true, 1000), dataCell("tests/test_s002_contract.py", C.white, false, 4000),
          dataCell("Contract", C.greenBg, true, 2000), dataCell("CREATE — new test file", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("14", C.white, true, 1000), dataCell("tests/test_s101_contract.py", C.white, false, 4000),
          dataCell("Contract", C.greenBg, true, 2000), dataCell("CREATE — new test file", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("15", C.white, true, 1000), dataCell("tests/test_s103_contract.py", C.white, false, 4000),
          dataCell("Contract", C.greenBg, true, 2000), dataCell("CREATE — new test file", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("16", C.white, true, 1000), dataCell("tests/test_s202_trace.py", C.white, false, 4000),
          dataCell("Contract", C.greenBg, true, 2000), dataCell("EDIT — add new test functions", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("17", C.white, true, 1000), dataCell("tests/test_s203_contract.py", C.white, false, 4000),
          dataCell("Contract", C.greenBg, true, 2000), dataCell("CREATE — new test file", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("18", C.white, true, 1000), dataCell("tests/test_s204_contract.py", C.white, false, 4000),
          dataCell("Contract", C.greenBg, true, 2000), dataCell("CREATE — new test file", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("19", C.white, true, 1000), dataCell("tests/test_s205_demo.py", C.white, false, 4000),
          dataCell("Contract", C.greenBg, true, 2000), dataCell("CREATE — new test file", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("20", C.white, true, 1000), dataCell("tests/test_s301_fly.py", C.white, false, 4000),
          dataCell("Contract", C.greenBg, true, 2000), dataCell("CREATE — new test file", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("21", C.white, true, 1000), dataCell("tests/test_s302_cicd.py", C.white, false, 4000),
          dataCell("Contract", C.greenBg, true, 2000), dataCell("CREATE — new test file", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("22", C.white, true, 1000), dataCell("tests/e2e/test_demo_ui.py", C.white, false, 4000),
          dataCell("Contract", C.greenBg, true, 2000), dataCell("CREATE — new Playwright E2E file", C.white, false, 2360),
        ]}),
        new TableRow({ children: [
          dataCell("23", C.white, true, 1000), dataCell(".gitignore", C.white, false, 4000),
          dataCell("Contract", C.greenBg, true, 2000), dataCell("EDIT — add .env.demo entry", C.white, false, 2360),
        ]}),
      ],
    }),
    spacer(2),
    h2("Migrations Needed"),
    twoColTable([
      ["Migration", "When required", true],
      ["None for FIX-001 through FIX-004", "No schema changes"],
      ["None for FIX-005 React frontend", "Static files only — no DB changes"],
      ["Verify models.py User.role enum", "If 'demo_viewer' is not a valid role value, add it (FIX-003)"],
    ], 4000, 5360),
    spacer(2),
    h2("Definition of Done"),
    para("All of the following must be true before this spec is considered complete:", { bold: true }),
    numbered("pytest tests/ -q passes with zero failures (including all new contract test files)"),
    numbered("playwright test tests/e2e/ passes against production URL"),
    numbered("grep 'auto_stop_machines' fly.toml shows 'false'"),
    numbered("grep 'saro-engine-1.0' routers/trace_view.py returns no matches"),
    numbered("curl https://{app}.fly.dev/api/v1/demo/token returns 200 with read_only=true"),
    numbered("curl -X POST https://{app}.fly.dev/api/v1/ingest with demo token returns 403"),
    numbered("GET /demo in browser shows live dashboard within 5 seconds — no Streamlit"),
    numbered("GitHub Actions deploy.yml health-check job passes — URL matches fly.toml app name"),
  ];
}

// ── Assemble and write ────────────────────────────────────────────────────────
async function main() {
  const doc = new Document({
    numbering: {
      config: [
        {
          reference: "bullets",
          levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } } }],
        },
        {
          reference: "numbers",
          levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } } }],
        },
      ],
    },
    styles: {
      default: { document: { run: { font: "Arial", size: 22 } } },
      paragraphStyles: [
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: 36, bold: true, font: "Arial" },
          paragraph: { spacing: { before: 400, after: 180 }, outlineLevel: 0 } },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: 28, bold: true, font: "Arial" },
          paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 } },
        { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: 24, bold: true, font: "Arial" },
          paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 } },
      ],
    },
    sections: [{
      properties: {
        page: { size: { width: 12240, height: 15840 },
                margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 } },
      },
      children: [
        ...coverPage(),
        ...auditSummary(),
        ...globalRules(),
        ...fix001(),
        ...fix002(),
        ...fix003(),
        ...fix004(),
        ...fix005(),
        ...contractTests(),
        ...filesChecklist(),
      ],
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  const outPath = path.join(__dirname, "..", "docs", "SARO_Fix_Spec_v1.0.docx");
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, buffer);
  console.log("Written:", outPath);
}

main().catch(e => { console.error(e); process.exit(1); });
