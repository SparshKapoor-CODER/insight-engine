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
C_DARK      = colors.HexColor("#0f172a")
C_PRIMARY   = colors.HexColor("#2563eb")
C_SECONDARY = colors.HexColor("#475569")
C_LIGHT_BG  = colors.HexColor("#eff6ff")
C_BORDER    = colors.HexColor("#bfdbfe")
C_ACCENT    = colors.HexColor("#16a34a")
C_WHITE     = colors.white
C_DIVIDER   = colors.HexColor("#e2e8f0")
C_COVER_BG  = colors.HexColor("#1e3a5f")


# ── Style definitions ────────────────────────────────────────────────────────
def _make_styles():
    s = getSampleStyleSheet()

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
        fontSize=13, fontName="Helvetica-Bold",
        textColor=C_PRIMARY, spaceAfter=6, spaceBefore=4
    )
    body = ParagraphStyle(
        "body_text",
        fontSize=10, fontName="Helvetica",
        textColor=C_DARK, spaceAfter=8, leading=17
    )
    chart_title = ParagraphStyle(
        "chart_title",
        fontSize=12, fontName="Helvetica-Bold",
        textColor=C_DARK, spaceAfter=4
    )
    page_label = ParagraphStyle(
        "page_label",
        fontSize=8, fontName="Helvetica",
        textColor=C_SECONDARY
    )

    return {
        "cover_title":    cover_title,
        "cover_sub":      cover_sub,
        "section_heading": section_heading,
        "body":           body,
        "chart_title":    chart_title,
        "page_label":     page_label,
    }


# ── Markdown bold → ReportLab bold converter ────────────────────────────────
def _md_to_rl(text: str, base_style: ParagraphStyle) -> Paragraph:
    """Convert **bold** markdown in LLM output to ReportLab <b> tags."""
    converted = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    return Paragraph(converted, base_style)


# ── Takeaway callout box ─────────────────────────────────────────────────────
def _takeaway_box(point: str, body_style: ParagraphStyle):
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', point)
    data = [[Paragraph(f"→  {text}", body_style)]]
    t = Table(data, colWidths=[6 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_LIGHT_BG),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BOX",           (0, 0), (-1, -1), 0.75, C_BORDER),
    ]))
    return t


# ── Cover page ───────────────────────────────────────────────────────────────
def _cover_page(story: list, plan: dict, styles: dict):
    # Dark blue cover background table
    title_text  = plan["report_title"]
    domain_text = plan["domain"].upper()
    date_text   = datetime.now().strftime("%B %d, %Y")

    cover_data = [[
        Paragraph(title_text, styles["cover_title"]),
    ]]
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
    story.append(Paragraph(f"Domain: {domain_text}", styles["cover_sub"]))
    story.append(Paragraph(f"Generated: {date_text}", styles["cover_sub"]))
    story.append(PageBreak())


# ── Main build function ──────────────────────────────────────────────────────
def build(chart_results: list, narrations: list, plan: dict, report_id: str) -> str:
    output_path = os.path.join(REPORTS_PATH, f"{report_id}.pdf")

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        rightMargin=inch, leftMargin=inch,
        topMargin=0.8 * inch, bottomMargin=0.8 * inch
    )

    styles         = _make_styles()
    narration_map  = {n["chart_id"]: n["insight_text"] for n in narrations}
    story          = []

    # ── Cover ────────────────────────────────────────────────────────────────
    _cover_page(story, plan, styles)

    # ── Executive Summary ────────────────────────────────────────────────────
    story.append(Paragraph("Executive Summary", styles["section_heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_DIVIDER, spaceAfter=8))
    story.append(_md_to_rl(plan["executive_summary"], styles["body"]))
    story.append(Spacer(1, 0.25 * inch))

    # ── Key Takeaways ────────────────────────────────────────────────────────
    story.append(Paragraph("Key Takeaways", styles["section_heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_DIVIDER, spaceAfter=8))
    for point in plan["key_takeaways"]:
        story.append(_takeaway_box(point, styles["body"]))
        story.append(Spacer(1, 0.08 * inch))

    story.append(PageBreak())

    # ── Charts ───────────────────────────────────────────────────────────────
    story.append(Paragraph("Analysis & Charts", styles["section_heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_DIVIDER, spaceAfter=12))

    for i, chart in enumerate(chart_results):
        # Chart number badge + title
        badge_text = f"<b>Chart {i + 1}</b>"
        story.append(Paragraph(badge_text, styles["page_label"]))
        story.append(Paragraph(chart["title"], styles["chart_title"]))
        story.append(Spacer(1, 0.08 * inch))

        # Chart image in a light bordered box
        img = Image(chart["png_path"], width=6 * inch, height=3 * inch)
        img_data = [[img]]
        img_table = Table(img_data, colWidths=[6.2 * inch])
        img_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX",           (0, 0), (-1, -1), 0.75, C_DIVIDER),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(img_table)
        story.append(Spacer(1, 0.12 * inch))

        # Insight text with bold numbers preserved
        insight = narration_map.get(chart["chart_id"], "")
        story.append(_md_to_rl(insight, styles["body"]))

        # Divider between charts, not after last one
        if i < len(chart_results) - 1:
            story.append(Spacer(1, 0.15 * inch))
            story.append(HRFlowable(
                width="100%", thickness=0.5,
                color=C_DIVIDER, spaceAfter=15
            ))

    doc.build(story)
    return output_path