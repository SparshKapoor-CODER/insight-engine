import io
import os
import re
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Image, PageBreak, Table, TableStyle, HRFlowable
)
from config import REPORTS_PATH

# ── Brand colors ────────────────────────────────────────────────────────────
C_DARK       = colors.HexColor("#0f172a")
C_PRIMARY    = colors.HexColor("#2563eb")
C_SECONDARY  = colors.HexColor("#475569")
C_LIGHT_BG   = colors.HexColor("#eff6ff")
C_BORDER     = colors.HexColor("#bfdbfe")
C_GREEN_BG   = colors.HexColor("#f0fdf4")
C_GREEN_BOR  = colors.HexColor("#86efac")
C_ORANGE_BG  = colors.HexColor("#fff7ed")
C_ORANGE_BOR = colors.HexColor("#fed7aa")
C_PURPLE_BG  = colors.HexColor("#faf5ff")
C_PURPLE_BOR = colors.HexColor("#d8b4fe")
C_WHITE      = colors.white
C_DIVIDER    = colors.HexColor("#e2e8f0")
C_COVER_BG   = colors.HexColor("#1e3a5f")


# ── Style definitions ────────────────────────────────────────────────────────
def _make_styles():
    cover_title = ParagraphStyle(
        "cover_title",
        fontSize=28, fontName="Helvetica-Bold",
        textColor=C_WHITE, spaceAfter=12, leading=36
    )
    cover_sub = ParagraphStyle(
        "cover_sub",
        fontSize=12, fontName="Helvetica",
        textColor=colors.HexColor("#93c5fd"), spaceAfter=6
    )
    section_heading = ParagraphStyle(
        "section_heading",
        fontSize=14, fontName="Helvetica-Bold",
        textColor=C_PRIMARY, spaceAfter=6, spaceBefore=4
    )
    body = ParagraphStyle(
        "body_text",
        fontSize=10, fontName="Helvetica",
        textColor=C_DARK, spaceAfter=8, leading=18
    )
    chart_title = ParagraphStyle(
        "chart_title",
        fontSize=13, fontName="Helvetica-Bold",
        textColor=C_DARK, spaceAfter=4
    )
    chart_insight = ParagraphStyle(
        "chart_insight",
        fontSize=10, fontName="Helvetica",
        textColor=C_DARK, spaceAfter=8, leading=19,
        leftIndent=4
    )
    page_label = ParagraphStyle(
        "page_label",
        fontSize=8, fontName="Helvetica",
        textColor=C_SECONDARY, spaceAfter=2
    )
    closing = ParagraphStyle(
        "closing",
        fontSize=10, fontName="Helvetica",
        textColor=C_DARK, spaceAfter=8, leading=18,
        borderColor=C_COVER_BG, borderWidth=0,
        leftIndent=0
    )

    return {
        "cover_title":     cover_title,
        "cover_sub":       cover_sub,
        "section_heading": section_heading,
        "body":            body,
        "chart_title":     chart_title,
        "chart_insight":   chart_insight,
        "page_label":      page_label,
        "closing":         closing,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────
def _md_to_rl(text: str, style: ParagraphStyle) -> Paragraph:
    """Convert **bold** markdown to ReportLab <b> tags."""
    converted = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    return Paragraph(converted, style)


def _callout_box(text: str, style: ParagraphStyle,
                 bg: colors.Color, border: colors.Color,
                 prefix: str = ""):
    """Generic styled callout box."""
    converted = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    content   = f"{prefix}{converted}" if prefix else converted
    data      = [[Paragraph(content, style)]]
    t         = Table(data, colWidths=[6.2 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), bg),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ("TOPPADDING",    (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("BOX",           (0, 0), (-1, -1), 0.75, border),
    ]))
    return t


# ── Cover page ────────────────────────────────────────────────────────────────
def _cover_page(story: list, plan: dict, styles: dict):
    cover_data  = [[Paragraph(plan["report_title"], styles["cover_title"])]]
    cover_table = Table(cover_data, colWidths=[6.5 * inch])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_COVER_BG),
        ("LEFTPADDING",   (0, 0), (-1, -1), 28),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 28),
        ("TOPPADDING",    (0, 0), (-1, -1), 36),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 36),
    ]))

    story.append(Spacer(1, 0.8 * inch))
    story.append(cover_table)
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(f"Domain: {plan['domain'].upper()}", styles["cover_sub"]))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", styles["cover_sub"]))
    story.append(PageBreak())


# ── Summary page (exec summary + takeaways) ───────────────────────────────────
def _summary_page(story: list, plan: dict, styles: dict):
    story.append(Paragraph("Executive Summary", styles["section_heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_DIVIDER, spaceAfter=8))
    story.append(_md_to_rl(plan["executive_summary"], styles["body"]))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Key Takeaways", styles["section_heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_DIVIDER, spaceAfter=8))
    for point in plan.get("key_takeaways", []):
        story.append(_callout_box(point, styles["body"], C_LIGHT_BG, C_BORDER, "→  "))
        story.append(Spacer(1, 0.07 * inch))

    story.append(PageBreak())


# ── One chart per page ────────────────────────────────────────────────────────
def _chart_pages(story: list, chart_results: list,
                 narration_map: dict, styles: dict):

    story.append(Paragraph("Analysis & Charts", styles["section_heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_DIVIDER, spaceAfter=10))

    for i, chart in enumerate(chart_results):
        story.append(Paragraph(f"Chart {i + 1} of {len(chart_results)}", styles["page_label"]))
        story.append(Paragraph(chart["title"], styles["chart_title"]))
        story.append(Spacer(1, 0.1 * inch))

        img       = Image(chart["png_path"], width=6.5 * inch, height=3.5 * inch)
        img_data  = [[img]]
        img_table = Table(img_data, colWidths=[6.5 * inch])
        img_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX",           (0, 0), (-1, -1), 0.75, C_DIVIDER),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(img_table)
        story.append(Spacer(1, 0.18 * inch))

        story.append(Paragraph("Insight", styles["section_heading"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=C_DIVIDER, spaceAfter=6))
        insight = narration_map.get(chart["chart_id"], "")
        story.append(_md_to_rl(insight, styles["chart_insight"]))

        if i < len(chart_results) - 1:
            story.append(PageBreak())


# ── Final client summary page ─────────────────────────────────────────────────
def _client_summary_page(story: list, plan: dict, styles: dict):
    story.append(PageBreak())
    story.append(Paragraph("Client Summary", styles["section_heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_DIVIDER, spaceAfter=10))

    story.append(Paragraph("Areas of Growth", styles["section_heading"]))
    for point in plan.get("growth_areas", []):
        story.append(_callout_box(point, styles["body"], C_GREEN_BG, C_GREEN_BOR, "📈  "))
        story.append(Spacer(1, 0.07 * inch))

    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("Areas to Focus On", styles["section_heading"]))
    for point in plan.get("focus_areas", []):
        story.append(_callout_box(point, styles["body"], C_ORANGE_BG, C_ORANGE_BOR, "⚠️  "))
        story.append(Spacer(1, 0.07 * inch))

    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("Recommendations", styles["section_heading"]))
    for i, rec in enumerate(plan.get("recommendations", []), 1):
        story.append(_callout_box(rec, styles["body"], C_PURPLE_BG, C_PURPLE_BOR, f"{i}.  "))
        story.append(Spacer(1, 0.07 * inch))

    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("Closing Note", styles["section_heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_DIVIDER, spaceAfter=8))
    closing_text  = plan.get("closing_summary", "")
    closing_style = ParagraphStyle(
        "closing_inner",
        fontSize=10, fontName="Helvetica",
        textColor=colors.HexColor("#1e3a5f"),
        leading=18, spaceAfter=0
    )
    story.append(_callout_box(
        closing_text, closing_style,
        colors.HexColor("#eff6ff"), colors.HexColor("#93c5fd")
    ))


# ── Change 4: helper to persist PDF bytes into the DB ────────────────────────
def store_pdf_in_db(report_id: str, pdf_path: str) -> None:
    """
    Read the PDF from disk and store it as a BLOB on the matching Report row.

    This is called *after* the PDF has been written to disk, so the disk copy
    acts as a fast local cache while the DB copy survives dyno restarts.

    Import is deferred to avoid circular imports at module load time.
    """
    try:
        from models.database import db, Report  # deferred import

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        report = Report.query.get(report_id)
        if report:
            report.pdf_data = pdf_bytes
            db.session.commit()
    except Exception as e:
        # Non-fatal — disk copy is still available if DB write fails
        print(f"WARNING: Could not store PDF BLOB for {report_id}: {e}")


# ── Main build ────────────────────────────────────────────────────────────────
def build(chart_results: list, narrations: list, plan: dict, report_id: str) -> str:
    output_path = os.path.join(REPORTS_PATH, f"{report_id}.pdf")

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        rightMargin=inch, leftMargin=inch,
        topMargin=0.8 * inch, bottomMargin=0.8 * inch
    )

    styles        = _make_styles()
    narration_map = {n["chart_id"]: n["insight_text"] for n in narrations}
    story         = []

    _cover_page(story, plan, styles)
    _summary_page(story, plan, styles)
    _chart_pages(story, chart_results, narration_map, styles)
    _client_summary_page(story, plan, styles)

    doc.build(story)

    # Change 4: persist to DB so the file survives ephemeral filesystem resets
    store_pdf_in_db(report_id, output_path)

    return output_path