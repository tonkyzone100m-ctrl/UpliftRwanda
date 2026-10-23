"""Executive Policy Brief PDF renderer (Module D).

Turns the brief_report.py payload into a print-ready A4 brief with reportlab
(platypus): banner, stat tables per survey layer, policy-engine verdicts with
severity chips, recommendations, and a methodology footer. Pure layout code —
all numbers come from `report` and cannot disagree with the CSV export.
"""

from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (HRFlowable, KeepTogether, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

INK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#475569")
FAINT = colors.HexColor("#94a3b8")
LINE = colors.HexColor("#e2e8f0")
EMERALD = colors.HexColor("#047857")
ROSE = colors.HexColor("#9f1239")
AMBER = colors.HexColor("#b45309")

SEVERITY_STYLES = {
    "critical": (ROSE, colors.HexColor("#fff1f2")),
    "attention": (AMBER, colors.HexColor("#fffbeb")),
    "strength": (EMERALD, colors.HexColor("#ecfdf5")),
    "info": (MUTED, colors.HexColor("#f1f5f9")),
}


def _hex(c) -> str:
    return "#" + c.hexval()[2:]


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontSize=19,
                                leading=23, textColor=INK, spaceAfter=2),
        "kicker": ParagraphStyle("kicker", parent=base["Normal"], fontSize=8.5,
                                 textColor=FAINT, spaceAfter=8),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=12.5,
                             textColor=INK, spaceBefore=6, spaceAfter=3),
        "sub": ParagraphStyle("sub", parent=base["Normal"], fontSize=8.5,
                              textColor=FAINT, spaceAfter=6),
        "body": ParagraphStyle("body", parent=base["Normal"], fontSize=9,
                               leading=13.5, textColor=MUTED, alignment=TA_JUSTIFY),
        "cell": ParagraphStyle("cell", parent=base["Normal"], fontSize=8.5, leading=11,
                               textColor=INK),
        "cellDim": ParagraphStyle("cellDim", parent=base["Normal"], fontSize=8,
                                  leading=10.5, textColor=FAINT),
        "bullet": ParagraphStyle("bullet", parent=base["Normal"], fontSize=9,
                                 leading=13, textColor=MUTED, leftIndent=8,
                                 bulletIndent=0, spaceAfter=3),
        "meta": ParagraphStyle("meta", parent=base["Normal"], fontSize=7.6,
                               leading=10.5, textColor=FAINT),
    }


def _value_html(row):
    """Value cell with a severity-tinted colour when far from the national ref."""
    color = INK
    value, bench, unit = row.get("value"), row.get("benchmark"), row.get("unit")
    if value is not None and bench is not None and unit == "%":
        worse_off = ("Poverty", "Extreme", "Vulnerable", "Out-of-Labour", "Inactivity",
                     "Unemployment", "NEET", "Informal", "Underutilization")
        worse_off_drop = ("Financial inclusion", "Formal", "Payment", "Digital", "Participation",
                          "Caseload", "Employment", "Timeliness", "TVET advantage", "Savings",
                          "Hunger", "Revenue")
        if value > bench + 5 and row["label"].startswith(worse_off):
            color = ROSE
        elif value < bench - 5 and row["label"].startswith(worse_off_drop):
            color = AMBER
    return f'{row["display"]}' if color is INK else \
        f'<font color="{_hex(color)}">{row["display"]}</font>'


def _stat_table(rows, styles):
    body = [[
        Paragraph("Indicator", styles["cellDim"]),
        Paragraph("Value", styles["cellDim"]),
        Paragraph("Reference (national)", styles["cellDim"]),
    ]]
    for row in rows:
        note = f' <font size="6.6" color="#94a3b8">· {row["note"]}</font>' if row.get("note") else ""
        label = Paragraph(f'<b>{row["label"]}</b>{note}', styles["cell"])
        value_cell = Paragraph(_value_html(row), styles["cell"])
        ref_cell = Paragraph(row["benchmark_display"], styles["cellDim"]) \
            if row.get("benchmark_display") else Paragraph("—", styles["cellDim"])
        body.append([label, value_cell, ref_cell])
    table = Table(body, colWidths=[80 * mm, 28 * mm, 47 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.35, colors.HexColor("#f1f5f9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def render(report) -> bytes:
    meta = report["meta"]
    styles = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=14 * mm, bottomMargin=16 * mm,
        title=f"UpliftRwanda Executive Policy Brief — {meta['district']}",
        author="UpliftRwanda · NISR 2026 Big Data Hackathon",
    )
    story = []

    scope_word = "National view · all 30 districts" if meta["scope"] == "national" else \
        f"{meta['province']} · {meta['area_type']}"
    story.append(Paragraph(
        "UPLIFTRWANDA · NISR 2026 BIG DATA HACKATHON · EXECUTIVE POLICY BRIEF", styles["kicker"]))
    story.append(Paragraph(f"{meta['district']} — data-backed status & actions", styles["title"]))
    story.append(Paragraph(scope_word + f" · generated {meta['generated_at']}", styles["sub"]))
    story.append(HRFlowable(width="100%", thickness=1.1, color=EMERALD, spaceAfter=8))

    for section in report["sections"]:
        block = []
        block.append(Paragraph(section["title"], styles["h2"]))
        if section.get("subtitle"):
            block.append(Paragraph(f"Source: {section['subtitle']}", styles["sub"]))
        block.append(_stat_table(section["rows"], styles))
        story.append(KeepTogether(block))
        story.append(Spacer(1, 6 * mm))

    if report["verdicts"]:
        verdict_rows = []
        for v in report["verdicts"]:
            fg, _bg = SEVERITY_STYLES.get(v.get("severity"), SEVERITY_STYLES["info"])
            chip = Paragraph(
                f'<font color="{_hex(fg)}"><b>{(v.get("severity") or "info").upper()}</b></font>',
                styles["cell"])
            headline = Paragraph(f'<b>{v.get("headline")}</b>', styles["cell"])
            pillar = Paragraph(v.get("pillar") or "", styles["cellDim"])
            verdict_rows.append([chip, headline, pillar])
        vt = Table(
            [[Paragraph("Severity", styles["cellDim"]),
              Paragraph("Engine verdict", styles["cellDim"]),
              Paragraph("Pillar", styles["cellDim"])],
             *verdict_rows],
            colWidths=[20 * mm, 116 * mm, 19 * mm], repeatRows=1)
        vt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fbfdfc")]),
            ("LINEBELOW", (0, 1), (-1, -1), 0.35, colors.HexColor("#f1f5f9")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        story.append(Paragraph("Policy-Engine Verdicts", styles["h2"]))
        story.append(Paragraph(
            "Thresholds follow the official rulebook; any ministerial edits surface live here.",
            styles["sub"]))
        story.append(vt)
        story.append(Spacer(1, 6 * mm))

    if report["recommendations"]:
        story.append(Paragraph("Recommended Actions", styles["h2"]))
        for i, rec in enumerate(report["recommendations"], start=1):
            story.append(Paragraph(f"<b>{i}.</b>  {rec}", styles["bullet"]))
        story.append(Spacer(1, 5 * mm))

    story.append(HRFlowable(width="100%", thickness=0.7, color=LINE, spaceBefore=4, spaceAfter=5))
    story.append(Paragraph("Methodology — " + meta["disclaimer"], styles["meta"]))
    story.append(Spacer(1, 2))
    story.append(Paragraph("Sources: " + " · ".join(meta["sources"]), styles["meta"]))
    story.append(Spacer(1, 2))
    story.append(Paragraph(
        "Generated by UpliftRwanda for the NISR 2026 Big Data Hackathon (Track 2) · "
        "GET /api/brief/{district} reproduces this document · interactive evidence: the UpliftRwanda dashboard.",
        styles["meta"]))

    doc.build(story)
    return buf.getvalue()
