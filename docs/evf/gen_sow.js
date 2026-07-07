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

function bold(text, size) {
  return new TextRun({ text, bold: true, font: FONT, size: size || 22 });
}
function normal(text, size) {
  return new TextRun({ text, font: FONT, size: size || 22 });
}
function para(runs, opts) {
  return new Paragraph({ children: Array.isArray(runs) ? runs : [runs], ...(opts || {}) });
}
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

// Parties table
function partiesTable() {
  const C1 = 3000, C2 = 6360;
  const rows = [
    ["SARO Entity", "SARO (Smart AI Risk Orchestrator) — [Legal Entity Name]"],
    ["SME Firm", "[Firm Name]"],
    ["Effective Date", "[DD Month YYYY]"],
  ];
  return new Table({
    columnWidths: [C1, C2],
    width: { size: C1 + C2, type: WidthType.DXA },
    rows: [
      new TableRow({ children: [labelCell("Party", C1), labelCell("Details", C2)] }),
      ...rows.map(([l, v]) => new TableRow({ children: [labelCell(l, C1), valueCell(v, C2)] })),
    ],
  });
}

// Framework scope table
function frameworkScopeTable() {
  const C1 = 2400, C2 = 3600, C3 = 3360;
  const rows = [
    [
      "EU AI Act",
      "Arts 9, 13, 17: Risk management, transparency, and accuracy documentation evidence support only. No legal classification.",
      "Qualified Compliance Opinion (QCO) — EU AI Act section",
    ],
    [
      "NIST AI RMF 1.0",
      "Govern, Map, Measure, Manage function areas evidence mapping. No RMF conformance statement.",
      "QCO — NIST AI RMF section",
    ],
    [
      "AIGP",
      "Principles evaluation supporting human-in-the-loop workflows. No AIGP certification.",
      "QCO — AIGP section",
    ],
    [
      "ISO 42001",
      "Document lifecycle linking for Clause 9 performance evaluation. No management system certification.",
      "QCO — ISO 42001 section",
    ],
  ];
  return new Table({
    columnWidths: [C1, C2, C3],
    width: { size: C1 + C2 + C3, type: WidthType.DXA },
    rows: [
      new TableRow({
        children: [labelCell("Framework", C1), labelCell("Locked Claim Scope", C2), labelCell("Deliverable", C3)],
      }),
      ...rows.map(([f, s, d]) =>
        new TableRow({
          children: [valueCell(f, C1), valueCell(s, C2), valueCell(d, C3)],
        })
      ),
    ],
  });
}

// Timeline table
function timelineTable() {
  const C1 = 1800, C2 = 3000, C3 = 1800, C4 = 2760;
  const rows = [
    ["1", "Document Review", "5 business days", "SME Firm"],
    ["2", "Product Demonstration", "2 business days", "SARO + SME Firm"],
    ["3", "Q&A and Gap Clarification", "3 business days", "SME Firm"],
    ["4", "Draft QCO Review Cycle (max 2 rounds)", "5 business days", "SME Firm + SARO Legal"],
  ];
  return new Table({
    columnWidths: [C1, C2, C3, C4],
    width: { size: C1 + C2 + C3 + C4, type: WidthType.DXA },
    rows: [
      new TableRow({
        children: [labelCell("Phase", C1), labelCell("Activity", C2), labelCell("Duration", C3), labelCell("Owner", C4)],
      }),
      ...rows.map(([p, a, d, o]) =>
        new TableRow({
          children: [valueCell(p, C1), valueCell(a, C2), valueCell(d, C3), valueCell(o, C4)],
        })
      ),
    ],
  });
}

// Fee table
function feeTable() {
  const C1 = 3000, C2 = 6360;
  const rows = [
    ["Fixed Fee", "[Amount] [Currency] — payable upon acceptance of final QCO"],
    ["Expense Policy", "Pre-approved reasonable travel and accommodation at cost; receipts required"],
    ["Invoice Terms", "Net 30 days from invoice date"],
  ];
  return new Table({
    columnWidths: [C1, C2],
    width: { size: C1 + C2, type: WidthType.DXA },
    rows: [
      new TableRow({ children: [labelCell("Item", C1), labelCell("Terms", C2)] }),
      ...rows.map(([l, v]) => new TableRow({ children: [labelCell(l, C1), valueCell(v, C2)] })),
    ],
  });
}

// Signature table
function sigTable() {
  const C1 = 2340, C2 = 2340, C3 = 2340, C4 = 2340;
  return new Table({
    columnWidths: [C1, C2, C3, C4],
    width: { size: C1 + C2 + C3 + C4, type: WidthType.DXA },
    rows: [
      new TableRow({
        children: [
          labelCell("SARO Product Owner", C1),
          labelCell("SARO Legal Counsel", C2),
          labelCell("SME Key Contact", C3),
          labelCell("SME Key Contact Title", C4),
        ],
      }),
      new TableRow({
        children: [
          valueCell("Signature: ________________", C1),
          valueCell("Signature: ________________", C2),
          valueCell("Signature: ________________", C3),
          valueCell("Title: ________________", C4),
        ],
      }),
      new TableRow({
        children: [
          valueCell("Date: ________________", C1),
          valueCell("Date: ________________", C2),
          valueCell("Date: ________________", C3),
          valueCell("Date: ________________", C4),
        ],
      }),
    ],
  });
}

function bulletPara(text) {
  return new Paragraph({
    children: [normal(text, 20)],
    bullet: { level: 0 },
    spacing: { after: 60 },
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
                new TextRun({ text: "SARO EVF-SOW-v1.0  |  Page ", font: FONT, size: 18 }),
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
          children: [bold("SARO External SME Validation Framework", 32)],
          alignment: AlignmentType.CENTER,
          spacing: { after: 120 },
        }),
        new Paragraph({
          children: [bold("Statement of Work Template", 28)],
          alignment: AlignmentType.CENTER,
          spacing: { after: 360 },
        }),

        sectionHeading("1. Parties"),
        partiesTable(),
        spacer(),

        sectionHeading("2. Framework Scope"),
        frameworkScopeTable(),
        spacer(),

        sectionHeading("3. Deliverable Format"),
        para([normal("The primary deliverable is a Qualified Compliance Opinion (QCO) document structured in accordance with FR-EVF-09, comprising nine mandatory sections:", 20)], { spacing: { after: 120 } }),
        bulletPara("Section 1: SME Identification and Credentials"),
        bulletPara("Section 2: Engagement Scope and Limitations Disclaimer"),
        bulletPara("Section 3: Framework Scope Boundary Statement"),
        bulletPara("Section 4: Review Methodology Summary"),
        bulletPara("Section 5: Findings per Framework Control/Article"),
        bulletPara("Section 6: Gap Register"),
        bulletPara("Section 7: Opinion Statement"),
        bulletPara("Section 8: Validity Period and Re-validation Trigger"),
        bulletPara("Section 9: SME Signature and Credential Reference"),
        para([normal("Refer to SARO EVF-QCO-v1.0 template for full structure and mandatory language requirements.", 20)], { spacing: { before: 120, after: 120 } }),
        spacer(),

        sectionHeading("4. Review Methodology"),
        bulletPara("Phase 1 — Document Review: SME Firm reviews SARO Evidence Package (classified CONFIDENTIAL) including architecture documentation, scoring engine specifications, TRACE timeline design, and compliance mapping artefacts."),
        bulletPara("Phase 2 — Product Demonstration: SARO team provides live or recorded product demonstration covering all in-scope framework features. SME may request clarification of specific capabilities."),
        bulletPara("Phase 3 — Q&A and Gap Clarification: Structured written Q&A exchange. SARO provides written responses within 2 business days of each query batch."),
        bulletPara("Phase 4 — Draft QCO Review Cycle: SARO Legal reviews draft QCO for factual accuracy and language compliance. Maximum two review rounds. SME retains editorial independence over professional opinion content."),
        spacer(),

        sectionHeading("5. Timeline"),
        timelineTable(),
        spacer(),

        sectionHeading("6. Fee Structure"),
        feeTable(),
        spacer(),

        sectionHeading("7. Confidentiality Obligations"),
        bulletPara("The SARO Evidence Package is classified CONFIDENTIAL and may be used solely for the purpose of this engagement."),
        bulletPara("The SME Firm shall not disclose any element of the Evidence Package to third parties without prior written consent from SARO Legal Counsel."),
        bulletPara("All Evidence Package materials must be returned or securely destroyed within 14 days of engagement completion. No retention beyond engagement close."),
        bulletPara("These obligations survive termination of this SOW for a period of five (5) years."),
        spacer(),

        sectionHeading("8. IP Assignment"),
        para([normal("The final QCO document becomes the exclusive property of SARO upon receipt of full payment. The SME Firm retains the right to describe the scope of this engagement in professional credentials and firm marketing materials, provided no SARO-confidential information is disclosed.", 20)], { spacing: { after: 120 } }),
        spacer(),

        sectionHeading("9. Scope Boundary Confirmation"),
        new Paragraph({
          children: [
            bold("Important: ", 20),
            normal("This Statement of Work does not constitute, and shall not be represented as constituting, a certification, conformity assessment, regulatory approval, or legal advice to SARO customers or any third party. The QCO deliverable is a professional opinion document for internal SARO governance purposes only.", 20),
          ],
          spacing: { after: 240 },
          border: {
            top: { style: BorderStyle.SINGLE, size: 6, color: "CC0000" },
            bottom: { style: BorderStyle.SINGLE, size: 6, color: "CC0000" },
            left: { style: BorderStyle.SINGLE, size: 6, color: "CC0000" },
            right: { style: BorderStyle.SINGLE, size: 6, color: "CC0000" },
          },
          shading: { type: ShadingType.CLEAR, color: "auto", fill: "FFF2CC" },
        }),
        spacer(),

        sectionHeading("10. Signatures"),
        sigTable(),
        spacer(),
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("C:\\Users\\shris\\SARO\\docs\\evf\\evf_sow_template.docx", buf);
  console.log("Created: C:\\Users\\shris\\SARO\\docs\\evf\\evf_sow_template.docx");
});
