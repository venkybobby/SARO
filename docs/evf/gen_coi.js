"use strict";
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, PageNumber, PageNumberElement, AlignmentType, WidthType,
  ShadingType, BorderStyle, HeadingLevel, LevelFormat, AbstractNumbering,
  Numbering, UnderlineType, PageOrientation, convertInchesToTwip,
  TableLayoutType
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
function spacer() {
  return para([normal("")]);
}

function labelCell(text, w) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, color: "auto", fill: "D9D9D9" },
    children: [para([bold(text, 20)])],
  });
}
function valueCell(text, w) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, color: "auto", fill: "FFFFFF" },
    children: [para([normal(text || "", 20)])],
  });
}

function sectionHeading(text) {
  return new Paragraph({
    children: [bold(text, 24)],
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 120 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "2F5496" } },
  });
}

function twoColTable(rows) {
  const COL1 = 3600, COL2 = 5760;
  return new Table({
    columnWidths: [COL1, COL2],
    width: { size: COL1 + COL2, type: WidthType.DXA },
    rows: rows.map(([label, value]) =>
      new TableRow({
        children: [labelCell(label, COL1), valueCell(value, COL2)],
      })
    ),
  });
}

function checkboxLine(checked, text) {
  const box = checked ? "[X]" : "[ ]";
  return para([normal(`${box}  ${text}`, 20)], { spacing: { after: 60 } });
}

function freeTextBox(label) {
  const W = 9360;
  return new Table({
    columnWidths: [W],
    width: { size: W, type: WidthType.DXA },
    rows: [
      new TableRow({
        children: [
          new TableCell({
            width: { size: W, type: WidthType.DXA },
            shading: { type: ShadingType.CLEAR, color: "auto", fill: "F2F2F2" },
            children: [
              para([bold(label + ":", 20)]),
              para([normal("", 20)]),
              para([normal("", 20)]),
              para([normal("", 20)]),
            ],
          }),
        ],
      }),
    ],
  });
}

function employmentTable() {
  const cols = [3000, 3000, 3360];
  return new Table({
    columnWidths: cols,
    width: { size: 9360, type: WidthType.DXA },
    rows: [
      new TableRow({
        children: [
          labelCell("Regulatory Body", cols[0]),
          labelCell("Role", cols[1]),
          labelCell("Dates (From – To)", cols[2]),
        ],
      }),
      ...[1, 2, 3].map(() =>
        new TableRow({
          children: [
            valueCell("", cols[0]),
            valueCell("", cols[1]),
            valueCell("", cols[2]),
          ],
        })
      ),
    ],
  });
}

function sigBlock() {
  const cols = [3000, 3000, 3360];
  const rows = [
    ["Declarant Name", "", ""],
    ["Title", "", ""],
    ["Firm", "", ""],
    ["Signature", "", ""],
    ["Date", "", ""],
  ];
  return new Table({
    columnWidths: cols,
    width: { size: 9360, type: WidthType.DXA },
    rows: [
      new TableRow({
        children: [
          labelCell("Field", cols[0]),
          labelCell("Declarant", cols[1]),
          labelCell("SARO Legal Counsel", cols[2]),
        ],
      }),
      ...rows.map(([field, dec, saro]) =>
        new TableRow({
          children: [
            labelCell(field, cols[0]),
            valueCell(dec, cols[1]),
            valueCell(saro, cols[2]),
          ],
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
              children: [
                new TextRun({ text: "CONFIDENTIAL — RESTRICTED | SARO EVF Programme", bold: true, font: FONT, size: 18, color: "CC0000" }),
              ],
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
                new TextRun({ text: "SARO EVF-COI-v1.0  |  Page ", font: FONT, size: 18 }),
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
        // Title
        new Paragraph({
          children: [bold("SARO External SME Validation Framework", 32)],
          alignment: AlignmentType.CENTER,
          spacing: { after: 120 },
        }),
        new Paragraph({
          children: [bold("Conflict of Interest Declaration Form", 28)],
          alignment: AlignmentType.CENTER,
          spacing: { after: 360 },
        }),

        // Section 1
        sectionHeading("1. SME Firm Details"),
        twoColTable([
          ["Firm Name", ""],
          ["Key Contact Name", ""],
          ["Key Contact Title", ""],
          ["Email", ""],
          ["Professional Credential", ""],
          ["Credential Body", ""],
          ["Credential Reference Number", ""],
        ]),
        spacer(),

        // Section 2
        sectionHeading("2. Part A — Prior or Current Commercial Relationship with SARO"),
        checkboxLine(false, "No relationship"),
        checkboxLine(false, "Current commercial relationship — describe below"),
        checkboxLine(false, "Prior relationship in last 3 years — describe below"),
        spacer(),
        freeTextBox("Description (if applicable)"),
        spacer(),

        // Section 3
        sectionHeading("3. Part B — Equity or Financial Interest in SARO Competitors"),
        checkboxLine(false, "None"),
        checkboxLine(false, "Yes — describe below"),
        spacer(),
        freeTextBox("Description (if applicable)"),
        spacer(),

        // Section 4
        sectionHeading("4. Part C — Employment History with Relevant Regulatory Bodies (last 3 years)"),
        checkboxLine(false, "None"),
        checkboxLine(false, "Yes — list body, role, and dates below"),
        spacer(),
        employmentTable(),
        spacer(),

        // Section 5
        sectionHeading("5. Declaration Statement"),
        new Paragraph({
          children: [
            normal(
              "I confirm the above information is complete and accurate. I understand that any material omission or misrepresentation will disqualify this firm from the SME engagement and may be reported to the relevant professional body.",
              20
            ),
          ],
          spacing: { after: 240 },
          border: {
            top: { style: BorderStyle.SINGLE, size: 6, color: "2F5496" },
            bottom: { style: BorderStyle.SINGLE, size: 6, color: "2F5496" },
            left: { style: BorderStyle.SINGLE, size: 6, color: "2F5496" },
            right: { style: BorderStyle.SINGLE, size: 6, color: "2F5496" },
          },
          shading: { type: ShadingType.CLEAR, color: "auto", fill: "EBF3FB" },
        }),
        spacer(),

        // Section 6
        sectionHeading("6. Signature Block"),
        para([bold("Declarant and SARO Legal Counsel Approval", 20)], { spacing: { after: 120 } }),
        sigBlock(),
        spacer(),
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("C:\\Users\\shris\\SARO\\docs\\evf\\evf_coi_declaration_form.docx", buf);
  console.log("Created: C:\\Users\\shris\\SARO\\docs\\evf\\evf_coi_declaration_form.docx");
});
