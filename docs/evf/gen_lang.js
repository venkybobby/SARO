"use strict";
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, PageNumber, PageNumberElement, AlignmentType, WidthType,
  ShadingType, BorderStyle, HeadingLevel, PageOrientation,
} = require("docx");
const fs = require("fs");

const FONT = "Arial";
const PAGE_W = 12240;
const PAGE_H = 15840;
const MARGIN = 1440;

function bold(text, size) { return new TextRun({ text, bold: true, font: FONT, size: size || 22 }); }
function normal(text, size) { return new TextRun({ text, font: FONT, size: size || 22 }); }
function para(runs, opts) { return new Paragraph({ children: Array.isArray(runs) ? runs : [runs], ...(opts || {}) }); }
function spacer() { return para([normal("")]); }

function sectionHeading(text) {
  return new Paragraph({
    children: [bold(text, 24)],
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 120 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "2F5496" } },
  });
}
function labelCell(text, w, fill) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, color: "auto", fill: fill || "D9D9D9" },
    children: [para([bold(text, 20)])],
  });
}
function valueCell(text, w, fill) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, color: "auto", fill: fill || "FFFFFF" },
    children: [para([normal(text || "", 20)])],
  });
}
function italic(text, size) { return new TextRun({ text, italics: true, font: FONT, size: size || 22 }); }
function bulletPara(text) {
  return new Paragraph({ children: [normal(text, 20)], bullet: { level: 0 }, spacing: { after: 60 } });
}

// Three tiers table — 4 rows x 5 cols
function tiersTable() {
  const C1 = 1440, C2 = 1800, C3 = 2400, C4 = 2160, C5 = 1560;
  const rows = [
    [
      "Tier 1",
      "QCO Issued",
      "QCO Issued: \"SARO has received a Qualified Compliance Opinion from [Firm] covering [framework scope]. The QCO is available to qualified reviewers under NDA.\"",
      "\"Based on our QCO, SARO v[X.X.X] supports evidence requirements for [framework] as assessed by [Firm].\"",
      "\"SARO is [framework] certified/compliant/approved\"",
    ],
    [
      "Tier 2",
      "Under Review",
      "\"SARO is currently undergoing independent expert review of its [framework] coverage. Results will be communicated upon completion.\"",
      "\"Our independent [framework] review is in progress. We expect to communicate outcomes in [timeframe].\"",
      "\"We expect to achieve [framework] compliance\"; \"SARO meets [framework] requirements\"",
    ],
    [
      "Tier 3",
      "Not Assessed / Current State",
      "No reference to framework coverage permitted until Tier 1 or Tier 2 status is achieved.",
      "If asked: \"SARO provides audit evidence supporting [framework] documentation workflows. We have not yet completed independent expert review of this coverage.\"",
      "Any positive claim of framework coverage, compliance, or certification",
    ],
  ];
  return new Table({
    columnWidths: [C1, C2, C3, C4, C5],
    width: { size: C1 + C2 + C3 + C4 + C5, type: WidthType.DXA },
    rows: [
      new TableRow({
        children: [
          labelCell("Tier", C1),
          labelCell("Condition", C2),
          labelCell("Approved Language Template", C3),
          labelCell("Example", C4),
          labelCell("Prohibited Variations", C5),
        ],
      }),
      ...rows.map(([t, c, a, e, p]) =>
        new TableRow({
          children: [
            valueCell(t, C1, t === "Tier 1" ? "D9EAD3" : t === "Tier 2" ? "FFF2CC" : "FCE5CD"),
            valueCell(c, C2),
            valueCell(a, C3),
            valueCell(e, C4),
            valueCell(p, C5, "FFCCCC"),
          ],
        })
      ),
    ],
  });
}

// Current framework status table
function statusTable() {
  const C1 = 2400, C2 = 1800, C3 = 4160;
  const rows = [
    ["EU AI Act", "Tier 3 — Internal Review Only", "No external claims permitted as of June 2026"],
    ["NIST AI RMF 1.0", "Tier 3 — Internal Review Only", "No external claims permitted as of June 2026"],
    ["AIGP", "Tier 3 — Internal Review Only", "No external claims permitted as of June 2026"],
    ["ISO 42001", "Tier 3 — Internal Review Only", "No external claims permitted as of June 2026"],
  ];
  return new Table({
    columnWidths: [C1, C2, C3],
    width: { size: C1 + C2 + C3, type: WidthType.DXA },
    rows: [
      new TableRow({ children: [labelCell("Framework", C1), labelCell("Current Tier Status", C2), labelCell("Notes", C3)] }),
      ...rows.map(([f, s, n]) =>
        new TableRow({ children: [valueCell(f, C1), valueCell(s, C2, "FCE5CD"), valueCell(n, C3)] })
      ),
    ],
  });
}

// Prohibited phrases table
function prohibitedTable() {
  const C1 = 4320, C2 = 5040;
  const rows = [
    ["NIST compliant", "\"SARO provides evidence supporting NIST AI RMF function areas\""],
    ["EU AI Act certified", "\"SARO generates indicators consistent with EU AI Act high-risk criteria\""],
    ["ISO 42001 certified", "\"SARO links audit records to ISO 42001 document lifecycle stages\""],
    ["AIGP certified", "\"SARO supports human-in-the-loop workflows for AIGP-certified reviewers\""],
    ["Audit passed", "\"TRACE evidence generated for auditor review\""],
    ["Compliance score", "\"Risk score: [X]/100\""],
    ["Regulatory approval", "\"SARO produces audit evidence — regulatory submission requires human sign-off\""],
    ["Certified tool", "\"SARO is an AI risk scoring tool with evidence-generation capabilities\""],
    ["Conformity assessed", "\"Independent expert review is in progress / has been completed (per Tier status)\""],
    ["Legally compliant", "\"SARO supports documentation workflows — legal determinations require qualified counsel\""],
  ];
  return new Table({
    columnWidths: [C1, C2],
    width: { size: C1 + C2, type: WidthType.DXA },
    rows: [
      new TableRow({ children: [labelCell("Forbidden Phrase", C1, "FFCCCC"), labelCell("Use Instead", C2, "D9EAD3")] }),
      ...rows.map(([f, u]) =>
        new TableRow({
          children: [valueCell(f, C1, "FFF2CC"), valueCell(u, C2)],
        })
      ),
    ],
  });
}

const doc = new Document({
  sections: [
    {
      properties: {
        page: {
          size: { width: PAGE_W, height: PAGE_H, orientation: PageOrientation.PORTRAIT },
          margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN },
        },
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              children: [new TextRun({ text: "INTERNAL POLICY  |  Owner: Product Owner  |  Effective: [Date]", bold: true, font: FONT, size: 18, color: "CC0000" })],
              alignment: AlignmentType.RIGHT,
            }),
          ],
        }),
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              children: [
                new TextRun({ text: "SARO EVF-LANG-v1.0  |  CONFIDENTIAL — INTERNAL  |  Page ", font: FONT, size: 18 }),
                new PageNumberElement(PageNumber.CURRENT),
                new TextRun({ text: " of ", font: FONT, size: 18 }),
                new PageNumberElement(PageNumber.TOTAL_PAGES),
              ],
              alignment: AlignmentType.CENTER,
            }),
          ],
        }),
      },
      children: [
        new Paragraph({
          children: [bold("SARO Compliance Claims Language Tier Policy", 32)],
          alignment: AlignmentType.CENTER,
          spacing: { after: 120 },
        }),
        new Paragraph({
          children: [bold("Approved Communication Tiers — External Use Only", 24)],
          alignment: AlignmentType.CENTER,
          spacing: { after: 360 },
        }),

        sectionHeading("1. Purpose and Scope"),
        para([bold("Who this policy applies to: ", 20), normal("All Sales, Product, and Engineering leads who communicate externally about SARO's capabilities.", 20)], { spacing: { after: 120 } }),
        para([bold("When it applies: ", 20), normal("Any external communication — written or verbal — that references SARO's coverage of or alignment to a compliance, regulatory, or governance framework (EU AI Act, NIST AI RMF, AIGP, ISO 42001, or any other).", 20)], { spacing: { after: 120 } }),
        para([normal("This policy is mandatory. Violations are subject to the enforcement process defined in Section 6.", 20)], { spacing: { after: 120 } }),
        spacer(),

        sectionHeading("2. The Three Tiers"),
        tiersTable(),
        spacer(),

        sectionHeading("3. Current Framework Status Table"),
        para([normal("Status as of June 2026:", 20)], { spacing: { after: 120 } }),
        statusTable(),
        spacer(),

        sectionHeading("4. Prohibited Phrases"),
        para([normal("The following phrases are strictly forbidden in any external communication. Use the approved alternatives provided.", 20)], { spacing: { after: 120 } }),
        prohibitedTable(),
        spacer(),

        sectionHeading("5. Escalation Protocol"),
        para([bold("If challenged on a compliance claim:", 20)], { spacing: { after: 120 } }),
        bulletPara("Step 1: Do not make additional claims or attempt to justify the challenged statement."),
        bulletPara("Step 2: Immediately escalate: Sales Team Lead → Legal Counsel → Product Owner within 2 hours of the challenge."),
        bulletPara("Step 3: Deliver the following holding statement to the challenger:"),
        new Paragraph({
          children: [
            italic("\"SARO is currently undergoing independent expert review of its framework coverage. We will provide a full written response within 24 hours.\"", 20),
          ],
          spacing: { before: 120, after: 240 },
          shading: { type: ShadingType.CLEAR, color: "auto", fill: "EBF3FB" },
          border: {
            top: { style: BorderStyle.SINGLE, size: 6, color: "2F5496" },
            bottom: { style: BorderStyle.SINGLE, size: 6, color: "2F5496" },
            left: { style: BorderStyle.SINGLE, size: 6, color: "2F5496" },
            right: { style: BorderStyle.SINGLE, size: 6, color: "2F5496" },
          },
        }),
        bulletPara("Step 4: Legal Counsel drafts written response; Product Owner approves before sending."),
        spacer(),

        sectionHeading("6. Enforcement"),
        bulletPara("A quarterly artefact audit of external communications (sales decks, website copy, emails, proposals) will be conducted by Legal Counsel and Product Owner."),
        bulletPara("Any identified violation will be reported to the Product Owner and Legal Counsel within 24 hours of discovery."),
        bulletPara("Violations are subject to disciplinary action in accordance with [Company Disciplinary Policy Reference — to be inserted]."),
        bulletPara("Repeat or wilful violations may be escalated to the relevant professional body if the individual holds a regulated credential."),
        spacer(),

        sectionHeading("7. Acknowledgement"),
        new Paragraph({
          children: [
            normal("I have read and understood the SARO Compliance Claims Language Tier Policy and agree to comply with all requirements.", 20),
          ],
          spacing: { after: 240 },
        }),
        new Table({
          columnWidths: [2340, 2340, 2340, 2340],
          width: { size: 9360, type: WidthType.DXA },
          rows: [
            new TableRow({
              children: [
                labelCell("Name", 2340), labelCell("Role", 2340),
                labelCell("Date", 2340), labelCell("Signature", 2340),
              ],
            }),
            new TableRow({
              children: [
                valueCell("", 2340), valueCell("", 2340),
                valueCell("", 2340), valueCell("", 2340),
              ],
            }),
          ],
        }),
        spacer(),
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("C:\\Users\\shris\\SARO\\docs\\evf\\evf_language_tier_policy.docx", buf);
  console.log("Created: C:\\Users\\shris\\SARO\\docs\\evf\\evf_language_tier_policy.docx");
});
