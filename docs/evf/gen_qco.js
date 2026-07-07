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
function italic(text, size) { return new TextRun({ text, italics: true, font: FONT, size: size || 22 }); }
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
function labelCell(text, w) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, color: "auto", fill: "D9D9D9" },
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
function bulletPara(text) {
  return new Paragraph({ children: [normal(text, 20)], bullet: { level: 0 }, spacing: { after: 60 } });
}

// Section 1: SME ID table
function smeIdTable() {
  const C1 = 3600, C2 = 5760;
  const rows = [
    ["Firm Name", ""],
    ["Individual Reviewer Name", ""],
    ["Professional Credential", ""],
    ["Credential Body", ""],
    ["Credential Reference Number", ""],
    ["Professional Indemnity Insurance Policy Ref", ""],
  ];
  return new Table({
    columnWidths: [C1, C2],
    width: { size: C1 + C2, type: WidthType.DXA },
    rows: rows.map(([l, v]) => new TableRow({ children: [labelCell(l, C1), valueCell(v, C2)] })),
  });
}

// Section 3: framework boundary table
function frameworkBoundaryTable() {
  const C1 = 2160, C2 = 7200;
  const rows = [
    ["EU AI Act", "Arts 9, 13, 17 evidence support only. SARO identifies characteristics consistent with high-risk criteria and transparency requirements. SARO does NOT classify systems under Annexes I-III or make legal determinations."],
    ["NIST AI RMF 1.0", "Govern, Map, Measure, Manage function area evidence mapping. SARO does NOT assert RMF conformance or assess organisational governance maturity."],
    ["AIGP", "Principles evaluation supporting human-in-the-loop workflows. SARO does NOT issue AIGP certifications or replace AIGP-certified human judgment."],
    ["ISO 42001", "Document lifecycle linking for Clause 9 (Performance Evaluation). SARO does NOT certify management systems or conduct Stage 1/Stage 2 audits."],
  ];
  return new Table({
    columnWidths: [C1, C2],
    width: { size: C1 + C2, type: WidthType.DXA },
    rows: [
      new TableRow({ children: [labelCell("Framework", C1), labelCell("Scope Boundary", C2)] }),
      ...rows.map(([f, s]) => new TableRow({ children: [valueCell(f, C1), valueCell(s, C2)] })),
    ],
  });
}

// Section 4: methodology summary table
function methodologyTable() {
  const C1 = 2400, C2 = 2160, C3 = 4800;
  return new Table({
    columnWidths: [C1, C2, C3],
    width: { size: C1 + C2 + C3, type: WidthType.DXA },
    rows: [
      new TableRow({ children: [labelCell("Phase", C1), labelCell("Date(s)", C2), labelCell("Documents / Activities", C3)] }),
      new TableRow({ children: [valueCell("1 — Document Review", C1), valueCell("", C2), valueCell("", C3)] }),
      new TableRow({ children: [valueCell("2 — Product Demonstration", C1), valueCell("", C2), valueCell("", C3)] }),
      new TableRow({ children: [valueCell("3 — Q&A and Gap Clarification", C1), valueCell("", C2), valueCell("", C3)] }),
      new TableRow({ children: [valueCell("4 — Draft QCO Review Cycle", C1), valueCell("", C2), valueCell("", C3)] }),
    ],
  });
}

// Section 5: findings table
function findingsTable() {
  const C1 = 1800, C2 = 2400, C3 = 1800, C4 = 2160, C5 = 1200;
  return new Table({
    columnWidths: [C1, C2, C3, C4, C5],
    width: { size: C1 + C2 + C3 + C4 + C5, type: WidthType.DXA },
    rows: [
      new TableRow({
        children: [
          labelCell("Control / Article", C1),
          labelCell("SARO Feature / Capability", C2),
          labelCell("Finding", C3),
          labelCell("Evidence Reference", C4),
          labelCell("Gap Flag (Y/N)", C5),
        ],
      }),
      ...[1, 2, 3, 4].map(() =>
        new TableRow({
          children: [
            valueCell("", C1), valueCell("", C2), valueCell("", C3),
            valueCell("", C4), valueCell("", C5),
          ],
        })
      ),
    ],
  });
}

// Section 6: gap register table
function gapRegisterTable() {
  const C1 = 1440, C2 = 2400, C3 = 2160, C4 = 1800, C5 = 1560;
  return new Table({
    columnWidths: [C1, C2, C3, C4, C5],
    width: { size: C1 + C2 + C3 + C4 + C5, type: WidthType.DXA },
    rows: [
      new TableRow({
        children: [
          labelCell("Gap ID", C1),
          labelCell("Description", C2),
          labelCell("Affected Framework Control", C3),
          labelCell("SARO Position", C4),
          labelCell("Recommended Action", C5),
        ],
      }),
      ...[1, 2, 3].map(() =>
        new TableRow({
          children: [
            valueCell("", C1), valueCell("", C2), valueCell("", C3),
            valueCell("", C4), valueCell("", C5),
          ],
        })
      ),
    ],
  });
}

// Section 9: signature block
function sigBlock9() {
  const C1 = 3120, C2 = 6240;
  const rows = [
    ["Reviewer Name", ""],
    ["Professional Credential", ""],
    ["Credential Body", ""],
    ["Registration / Licence Reference", ""],
    ["Signature", ""],
    ["Date", ""],
  ];
  return new Table({
    columnWidths: [C1, C2],
    width: { size: C1 + C2, type: WidthType.DXA },
    rows: rows.map(([l, v]) => new TableRow({ children: [labelCell(l, C1), valueCell(v, C2)] })),
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
              children: [new TextRun({ text: "CONFIDENTIAL — RESTRICTED | SARO EVF Programme", bold: true, font: FONT, size: 18, color: "CC0000" })],
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
                new TextRun({ text: "SARO EVF-QCO-v1.0  |  QCO Ref: [number]  |  Page ", font: FONT, size: 18 }),
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
        // Prohibited language warning
        new Paragraph({
          children: [
            bold("PROHIBITED LANGUAGE: ", 20),
            bold('This document must NOT use the words "certified", "certification", "conformity assessment", or "compliant" to describe SARO\'s status.', 20),
          ],
          spacing: { after: 240 },
          border: {
            top: { style: BorderStyle.SINGLE, size: 12, color: "CC0000" },
            bottom: { style: BorderStyle.SINGLE, size: 12, color: "CC0000" },
            left: { style: BorderStyle.SINGLE, size: 12, color: "CC0000" },
            right: { style: BorderStyle.SINGLE, size: 12, color: "CC0000" },
          },
          shading: { type: ShadingType.CLEAR, color: "auto", fill: "FFCCCC" },
        }),
        spacer(),

        // Title block
        new Paragraph({
          children: [bold("SARO External SME Validation Framework", 32)],
          alignment: AlignmentType.CENTER,
          spacing: { after: 120 },
        }),
        new Paragraph({
          children: [bold("Qualified Compliance Opinion [TEMPLATE]", 28)],
          alignment: AlignmentType.CENTER,
          spacing: { after: 120 },
        }),
        new Paragraph({
          children: [italic("QCO Reference: SARO-QCO-[FRAMEWORK]-[YYYY]-[SEQ]", 22)],
          alignment: AlignmentType.CENTER,
          spacing: { after: 360 },
        }),

        // Section 1
        sectionHeading("1. SME Identification and Credentials"),
        smeIdTable(),
        spacer(),

        // Section 2
        sectionHeading("2. Engagement Scope and Limitations Disclaimer"),
        new Paragraph({
          children: [
            bold("This document is a qualified professional opinion based on document review and product demonstration. It does not constitute regulatory certification, legal advice, conformity assessment, or compliance approval. Human review and sign-off by qualified personnel is required before any regulatory submission.", 22),
          ],
          spacing: { after: 240 },
          border: {
            top: { style: BorderStyle.SINGLE, size: 8, color: "CC0000" },
            bottom: { style: BorderStyle.SINGLE, size: 8, color: "CC0000" },
            left: { style: BorderStyle.SINGLE, size: 8, color: "CC0000" },
            right: { style: BorderStyle.SINGLE, size: 8, color: "CC0000" },
          },
          shading: { type: ShadingType.CLEAR, color: "auto", fill: "FFF2CC" },
        }),
        spacer(),

        // Section 3
        sectionHeading("3. Framework Scope Boundary Statement"),
        frameworkBoundaryTable(),
        spacer(),

        // Section 4
        sectionHeading("4. Review Methodology Summary"),
        methodologyTable(),
        spacer(),

        // Section 5
        sectionHeading("5. Findings per Framework Control / Article"),
        findingsTable(),
        spacer(),

        // Section 6
        sectionHeading("6. Gap Register"),
        gapRegisterTable(),
        spacer(),

        // Section 7
        sectionHeading("7. Opinion Statement"),
        new Paragraph({
          children: [
            normal("Based on our review of SARO v[X.X.X] conducted between [start date] and [end date], it is our qualified opinion that SARO ", 20),
            bold("[supports / partially supports / does not support]", 20),
            normal(" the evidence requirements for [framework scope]. This opinion is valid for [SARO version assessed] only and expires on ", 20),
            bold("[expiry date]", 20),
            normal(".", 20),
          ],
          spacing: { before: 120, after: 240 },
          shading: { type: ShadingType.CLEAR, color: "auto", fill: "EBF3FB" },
        }),
        spacer(),

        // Section 8
        sectionHeading("8. Validity Period and Re-validation Trigger"),
        new Paragraph({
          children: [bold("Expiry Date: ", 20), normal("[Date — maximum 12 months from opinion date]", 20)],
          spacing: { after: 120 },
        }),
        para([bold("This QCO is invalidated early upon any of the following events:", 20)], { spacing: { after: 120 } }),
        bulletPara("Material change to SARO scoring engine (DIR formula, SHAP weighting, or KS-test thresholds)"),
        bulletPara("Release of a new SARO major or minor version (e.g., v8.x to v9.0 or v8.0 to v8.1)"),
        bulletPara("Change to framework scope covered by this QCO (e.g., addition or removal of covered articles)"),
        bulletPara("Regulatory update to any covered framework that materially changes the evidence requirements"),
        bulletPara("Material change to SARO TRACE timeline architecture or hash-chain integrity mechanism"),
        spacer(),

        // Section 9
        sectionHeading("9. SME Signature and Credential Reference"),
        new Paragraph({
          children: [
            italic("This opinion was prepared by [Name], [Credential], [Body]. Registration/licence reference: [ref].", 20),
          ],
          spacing: { after: 240 },
        }),
        sigBlock9(),
        spacer(),
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("C:\\Users\\shris\\SARO\\docs\\evf\\evf_qco_template.docx", buf);
  console.log("Created: C:\\Users\\shris\\SARO\\docs\\evf\\evf_qco_template.docx");
});
