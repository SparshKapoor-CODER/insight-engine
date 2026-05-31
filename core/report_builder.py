# report_builder.py  —  Insight Engine PDF Report Builder
# ==========================================================
# Produces a high-end, management-consulting-grade PDF report.
#
# Public API (unchanged):
#     build(chart_results, narrations, plan, report_id,
#           company_name="Client", brand_color_hex="#2563eb") -> str
#
# All content (text, chart images) is passed in unchanged.
# This module controls only layout, typography, spacing, colors, and decorative elements.
#

import io
import os
import re
import math
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Image, PageBreak, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from reportlab.graphics.shapes import Drawing, Path, Circle
from reportlab.graphics import renderPDF

from config import REPORTS_PATH

# ══════════════════════════════════════════════════════════════════════════════
# Static neutral palette — never changes with brand color
# ══════════════════════════════════════════════════════════════════════════════
C_INK       = colors.HexColor("#1e293b")   # near-black, main body text
C_INK_2     = colors.HexColor("#334155")   # insight body text (slightly softer)
C_INK_3     = colors.HexColor("#64748b")   # secondary / metadata
C_DIVIDER   = colors.HexColor("#e2e8f0")   # thin rules
C_RULE_SOFT = colors.HexColor("#cbd5e1")   # footer lines, scope separators
C_BG_PAGE   = colors.HexColor("#f8fafc")   # page paper tint
C_BG_CARD   = colors.HexColor("#f1f5f9")   # subtle card backgrounds
C_WHITE     = colors.white

# Growth / Focus / Recommendations card palettes (neutral, brand-agnostic)
_GROWTH_BG  = colors.HexColor("#f0fdf4")
_GROWTH_ACC = colors.HexColor("#16a34a")
_FOCUS_BG   = colors.HexColor("#fefce8")
_FOCUS_ACC  = colors.HexColor("#ca8a04")
_REC_BG     = colors.HexColor("#f5f3ff")
_REC_ACC    = colors.HexColor("#7c3aed")


# ══════════════════════════════════════════════════════════════════════════════
# Color math helpers  (pure stdlib hex arithmetic, no colorsys)
# ══════════════════════════════════════════════════════════════════════════════

def _hex_to_rgb(hex_str: str) -> tuple:
    h = hex_str.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
    )


def _darken(hex_str: str, pct: float) -> str:
    r, g, b = _hex_to_rgb(hex_str)
    f = 1.0 - pct / 100.0
    return _rgb_to_hex(int(r * f), int(g * f), int(b * f))


def _lighten(hex_str: str, pct: float) -> str:
    r, g, b = _hex_to_rgb(hex_str)
    f = pct / 100.0
    return _rgb_to_hex(
        int(r + (255 - r) * f),
        int(g + (255 - g) * f),
        int(b + (255 - b) * f),
    )


# ══════════════════════════════════════════════════════════════════════════════
# SVG Logo → ReportLab Drawing
# ══════════════════════════════════════════════════════════════════════════════
# Original SVG viewBox="0 0 28 28":
#   <rect x="2"  y="14" width="5" height="12" rx="2" opacity="1.0"/>
#   <rect x="10" y="8"  width="5" height="18" rx="2" opacity="0.7"/>
#   <rect x="18" y="2"  width="5" height="24" rx="2" opacity="0.4"/>
#   <circle cx="21" cy="2" r="3"/>
#
# We translate SVG coordinates (top-left origin, y down) to
# ReportLab coordinates (bottom-left origin, y up).

_LOGO_SVG_SIZE = 28.0        # viewBox dimension (square)
_LOGO_TARGET_W = 2.8 * inch  # watermark render width


def _make_logo_drawing(fill_hex: str = "#e2e8f0") -> Drawing:
    """
    Build a ReportLab Drawing that replicates the Insight Engine SVG logo.
    The shapes are drawn with Path (rounded rects) and Circle.
    `fill_hex` controls the color; opacity per element is baked in.
    """
    scale = _LOGO_TARGET_W / _LOGO_SVG_SIZE
    VH    = _LOGO_SVG_SIZE       # SVG viewport height
    fc    = colors.HexColor(fill_hex)

    def _rr(x, y, w, h, rx, alpha):
        """Approximate rounded rect in ReportLab y-up coordinates."""
        rl_x = x * scale
        rl_y = (VH - y - h) * scale
        rl_w = w * scale
        rl_h = h * scale
        r    = rx * scale
        p = Path(fillColor=fc, strokeColor=None, fillOpacity=alpha)
        # Walk the rounded-rectangle outline (8-arc approximation)
        p.moveTo(rl_x + r, rl_y + rl_h)
        p.lineTo(rl_x + rl_w - r, rl_y + rl_h)
        p.curveTo(rl_x+rl_w-r, rl_y+rl_h,
                  rl_x+rl_w,   rl_y+rl_h,
                  rl_x+rl_w,   rl_y+rl_h-r)
        p.lineTo(rl_x + rl_w, rl_y + r)
        p.curveTo(rl_x+rl_w, rl_y+r,
                  rl_x+rl_w, rl_y,
                  rl_x+rl_w-r, rl_y)
        p.lineTo(rl_x + r, rl_y)
        p.curveTo(rl_x+r, rl_y,
                  rl_x,   rl_y,
                  rl_x,   rl_y+r)
        p.lineTo(rl_x, rl_y + rl_h - r)
        p.curveTo(rl_x, rl_y+rl_h-r,
                  rl_x, rl_y+rl_h,
                  rl_x+r, rl_y+rl_h)
        p.closePath()
        return p

    def _circle(cx, cy, r_svg, alpha):
        return Circle(
            cx * scale, (VH - cy) * scale, r_svg * scale,
            fillColor=fc, strokeColor=None, fillOpacity=alpha,
        )

    d = Drawing(_LOGO_TARGET_W, _LOGO_TARGET_W)
    d.add(_rr( 2, 14, 5, 12, 2, 1.0))   # bar 1
    d.add(_rr(10,  8, 5, 18, 2, 0.7))   # bar 2
    d.add(_rr(18,  2, 5, 24, 2, 0.4))   # bar 3
    d.add(_circle(21, 2, 3, 1.0))        # dot accent
    return d


# ══════════════════════════════════════════════════════════════════════════════
# Canvas callbacks  (watermark + page numbers)
# ══════════════════════════════════════════════════════════════════════════════

def _make_page_callbacks(brand_hex: str, total_pages_ref: list):
    """
    Returns (first_page_cb, later_pages_cb).

    first_page_cb   — draws full-bleed dark cover background + logo watermark
    later_pages_cb  — draws logo watermark + footer rule + page number

    total_pages_ref is a mutable list [N] so the callback can read the
    final page count after the doc is built (two-pass trick not needed here;
    we just use doc.page for current page number and omit total if unknown).
    """
    logo_drawing = _make_logo_drawing("#e2e8f0")   # light grey logo
    cover_bg_hex = _darken(brand_hex, 35)
    cover_bg     = colors.HexColor(cover_bg_hex)

    def _draw_logo_watermark(canvas, doc):
        """Shared: diagonal logo watermark, behind content."""
        canvas.saveState()
        pw, ph = doc.pagesize
        canvas.translate(pw / 2, ph / 2)
        canvas.rotate(45)
        canvas.translate(-_LOGO_TARGET_W / 2, -_LOGO_TARGET_W / 2)
        # Render with global alpha ~0.10
        canvas.setFillAlpha(0.10)
        renderPDF.draw(logo_drawing, canvas, 0, 0, showBoundary=False)
        canvas.restoreState()

    def _draw_footer(canvas, doc):
        """Shared: thin rule + page number."""
        canvas.saveState()
        pw, ph = doc.pagesize
        left  = doc.leftMargin
        right = pw - doc.rightMargin
        y_rule = doc.bottomMargin * 0.6
        y_text = doc.bottomMargin * 0.35

        canvas.setStrokeColor(C_RULE_SOFT)
        canvas.setLineWidth(0.4)
        canvas.line(left, y_rule, right, y_rule)

        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(C_INK_3)
        canvas.drawRightString(right, y_text, f"Page {doc.page}")
        canvas.restoreState()

    def _cover_bg_cb(canvas, doc):
        """Cover page: full-bleed background only (no footer, no watermark)."""
        canvas.saveState()
        pw, ph = doc.pagesize
        canvas.setFillColor(cover_bg)
        canvas.rect(0, 0, pw, ph, fill=1, stroke=0)
        canvas.restoreState()

    def first_page_cb(canvas, doc):
        _cover_bg_cb(canvas, doc)
        # No watermark on cover — it would be invisible on dark bg

    def later_pages_cb(canvas, doc):
        _draw_logo_watermark(canvas, doc)
        _draw_footer(canvas, doc)

    return first_page_cb, later_pages_cb


# ══════════════════════════════════════════════════════════════════════════════
# Style factory
# ══════════════════════════════════════════════════════════════════════════════

def _make_styles(C_BRAND: colors.Color, brand_hex: str) -> dict:
    """
    Return all ParagraphStyles keyed by name.
    C_BRAND is the dynamic brand color derived from brand_color_hex.
    Signature intentionally unchanged from previous version.
    """
    brand_light = colors.HexColor(_lighten(brand_hex, 92))

    cover_company = ParagraphStyle(
        "cover_company",
        fontSize=34, fontName="Times-Bold",
        textColor=C_WHITE, leading=42, spaceAfter=6,
    )
    cover_title_style = ParagraphStyle(
        "cover_title_style",
        fontSize=16, fontName="Helvetica",
        textColor=colors.HexColor("#cbd5e1"), leading=22, spaceAfter=10,
    )
    cover_prepared = ParagraphStyle(
        "cover_prepared",
        fontSize=9.5, fontName="Helvetica",
        textColor=colors.HexColor("#94a3b8"), leading=15, spaceAfter=4,
    )
    cover_date = ParagraphStyle(
        "cover_date",
        fontSize=9, fontName="Helvetica",
        textColor=colors.HexColor("#64748b"), leading=14, spaceAfter=0,
    )
    cover_domain = ParagraphStyle(
        "cover_domain",
        fontSize=8, fontName="Helvetica-Bold",
        textColor=C_WHITE, leading=12, spaceAfter=0,
        letterSpacing=2.0,
    )
    cover_confidential = ParagraphStyle(
        "cover_confidential",
        fontSize=7.5, fontName="Helvetica",
        textColor=colors.HexColor("#475569"),
        leading=11, spaceAfter=0, letterSpacing=0.8,
    )
    section_heading = ParagraphStyle(
        "section_heading",
        fontSize=16, fontName="Times-Bold",
        textColor=C_BRAND, spaceAfter=4, spaceBefore=6, leading=20,
    )
    body = ParagraphStyle(
        "body_text",
        fontSize=10, fontName="Helvetica",
        textColor=C_INK_2, spaceAfter=10, leading=17,
        alignment=4,   # JUSTIFY
    )
    chart_title_style = ParagraphStyle(
        "chart_title_style",
        fontSize=14, fontName="Helvetica-Bold",
        textColor=C_INK, spaceAfter=2, leading=18,
    )
    chart_counter = ParagraphStyle(
        "chart_counter",
        fontSize=7.5, fontName="Helvetica",
        textColor=C_INK_3, spaceAfter=3, alignment=2,  # right-align
    )
    insight_label = ParagraphStyle(
        "insight_label",
        fontSize=7.5, fontName="Helvetica-Bold",
        textColor=C_BRAND, spaceAfter=2, leading=11, letterSpacing=1.8,
    )
    chart_insight = ParagraphStyle(
        "chart_insight",
        fontSize=10, fontName="Helvetica",
        textColor=C_INK_2, spaceAfter=6, leading=17,
        alignment=4,
    )
    chart_footer_style = ParagraphStyle(
        "chart_footer_style",
        fontSize=7.5, fontName="Helvetica",
        textColor=C_INK_3, leading=11, spaceAfter=0,
        alignment=2,  # right-align
    )
    scope_label = ParagraphStyle(
        "scope_label",
        fontSize=7, fontName="Helvetica-Bold",
        textColor=C_INK_3, spaceAfter=3,
        letterSpacing=1.2,
    )
    scope_value = ParagraphStyle(
        "scope_value",
        fontSize=11, fontName="Helvetica-Bold",
        textColor=C_BRAND, spaceAfter=0, leading=14,
    )
    takeaway_text = ParagraphStyle(
        "takeaway_text",
        fontSize=10, fontName="Helvetica",
        textColor=C_INK_2, spaceAfter=0, leading=17,
    )
    card_text = ParagraphStyle(
        "card_text",
        fontSize=10, fontName="Helvetica",
        textColor=C_INK_2, spaceAfter=0, leading=17,
    )
    closing_text = ParagraphStyle(
        "closing_text",
        fontSize=10, fontName="Helvetica",
        textColor=C_INK_2, leading=17, spaceAfter=0,
        alignment=4,
    )
    rec_num = ParagraphStyle(
        "rec_num",
        fontSize=10, fontName="Helvetica-Bold",
        textColor=C_BRAND, leading=17, spaceAfter=0,
    )
    client_header = ParagraphStyle(
        "client_header",
        fontSize=20, fontName="Times-Bold",
        textColor=C_BRAND, spaceAfter=4, leading=26,
    )

    return {
        "cover_company":    cover_company,
        "cover_title":      cover_title_style,
        "cover_prepared":   cover_prepared,
        "cover_date":       cover_date,
        "cover_domain":     cover_domain,
        "cover_confidential": cover_confidential,
        "section_heading":  section_heading,
        "body":             body,
        "chart_title":      chart_title_style,
        "chart_counter":    chart_counter,
        "insight_label":    insight_label,
        "chart_insight":    chart_insight,
        "chart_footer":     chart_footer_style,
        "scope_label":      scope_label,
        "scope_value":      scope_value,
        "takeaway_text":    takeaway_text,
        "card_text":        card_text,
        "closing_text":     closing_text,
        "rec_num":          rec_num,
        "client_header":    client_header,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Content helpers
# ══════════════════════════════════════════════════════════════════════════════

def _md_to_rl(text: str, style: ParagraphStyle) -> Paragraph:
    """Convert **bold** markdown to ReportLab <b> tags."""
    converted = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    return Paragraph(converted, style)


def _thin_rule(color=None, thickness=0.4, space_before=2, space_after=6):
    return HRFlowable(
        width="100%",
        thickness=thickness,
        color=color or C_DIVIDER,
        spaceBefore=space_before,
        spaceAfter=space_after,
        dash=None,
    )


def _section_head(title: str, styles: dict) -> list:
    """Section heading + thin brand-colored rule."""
    return [
        Paragraph(title, styles["section_heading"]),
        _thin_rule(color=colors.HexColor("#e2e8f0"), thickness=0.5, space_before=2, space_after=10),
    ]


def _left_border_card(text: str, style: ParagraphStyle,
                      bg: colors.Color, accent: colors.Color,
                      prefix: str = "") -> Table:
    """
    Card with:
      - soft background fill
      - 3pt left border accent (brand or section color)
      - no outer BOX border (clean look)
    """
    converted = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    content   = f"{prefix}{converted}" if prefix else converted
    t = Table([[Paragraph(content, style)]], colWidths=[6.2 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), bg),
        ("TOPPADDING",    (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
        ("LEFTPADDING",   (0, 0), (-1, -1), 18),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ("LINEBEFORE",    (0, 0), ( 0, -1),  3, accent),
    ]))
    return t


# Keep the old _callout_box name as an alias so any direct callers still work
def _callout_box(text, style, bg, border, prefix=""):
    return _left_border_card(text, style, bg, border, prefix)


# ══════════════════════════════════════════════════════════════════════════════
# Cover page  (full-bleed, drawn via canvas callback)
# ══════════════════════════════════════════════════════════════════════════════

def _cover_page(story: list, plan: dict, styles: dict,
                company_name: str, C_BRAND: colors.Color,
                brand_hex: str):
    """
    Premium cover page.

    The dark background is drawn via the first_page canvas callback
    (full-bleed). Here we only add flowable content that will be
    composited on top of that background.

    Layout (top → bottom):
      [generous top space]
      Company name         — large serif, white
      Thin brand accent line
      Report title         — medium sans, light grey
      "Prepared by …" + date
      [flexible gap]
      Domain pill
      [bottom space]
      Confidentiality line
    """
    date_str = datetime.now().strftime("%B %d, %Y")

    # All text on the cover sits on a dark background, so colors must be light
    brand_light_hex = _lighten(brand_hex, 60)
    C_BRAND_LIGHT   = colors.HexColor(brand_light_hex)

    # Top breathing room
    story.append(Spacer(1, 1.6 * inch))

    # Company name
    story.append(Paragraph(company_name, styles["cover_company"]))

    # Thin accent line (brand color)
    story.append(_thin_rule(color=C_BRAND_LIGHT, thickness=1.2,
                             space_before=4, space_after=14))

    # Report title
    story.append(Paragraph(plan["report_title"], styles["cover_title"]))

    story.append(Spacer(1, 0.18 * inch))

    # Prepared by + date (stacked, subtle)
    story.append(Paragraph("Prepared by Insight Engine", styles["cover_prepared"]))
    story.append(Paragraph(date_str, styles["cover_date"]))

    # Push domain pill toward lower third
    story.append(Spacer(1, 1.5 * inch))

    # Domain pill — small table acting as a capsule
    pill_style = ParagraphStyle(
        "pill_inner", fontSize=8, fontName="Helvetica-Bold",
        textColor=C_WHITE, leading=11, letterSpacing=2.0,
    )
    pill_data  = [[Paragraph(plan.get("domain", "").upper(), pill_style)]]
    pill_table = Table(pill_data, colWidths=[2.4 * inch])
    pill_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_BRAND_LIGHT),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
    ]))
    story.append(pill_table)

    story.append(Spacer(1, 0.55 * inch))

    # Confidentiality line
    story.append(Paragraph(
        f"CONFIDENTIAL  ·  Prepared exclusively for {company_name}",
        styles["cover_confidential"],
    ))

    story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
# Executive Summary page
# ══════════════════════════════════════════════════════════════════════════════

def _summary_page(story: list, plan: dict, styles: dict,
                  chart_count: int, domain: str,
                  C_BRAND: colors.Color, C_BRAND_HEX: str):
    """
    Page 2 — Executive Summary + Report Scope + Key Takeaways.

    Developer note — executive_summary field expectations:
      - Maximum 5 sentences, no generic filler
      - Opens with the single most important finding
      - Tone: senior management consulting, direct and data-driven
    """
    date_str    = datetime.now().strftime("%B %d, %Y")
    brand_light = colors.HexColor(_lighten(C_BRAND_HEX, 92))

    # ── Section heading ──────────────────────────────────────────────────────
    for el in _section_head("Executive Summary", styles):
        story.append(el)

    # Body text with optional drop-cap visual: a left accent bar
    exec_text = plan.get("executive_summary", "")
    exec_card = Table(
        [[_md_to_rl(exec_text, styles["body"])]],
        colWidths=[6.2 * inch],
    )
    exec_card.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING",   (0, 0), (-1, -1), 20),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
        ("LINEBEFORE",    (0, 0), ( 0, -1),  4, C_BRAND),
    ]))
    story.append(exec_card)
    story.append(Spacer(1, 0.28 * inch))

    # ── Report Scope — three-column horizontal strip ─────────────────────────
    scope_bg  = colors.HexColor(_lighten(C_BRAND_HEX, 94))
    scope_bor = C_BRAND

    scope_header_row = [
        Paragraph("CHARTS", styles["scope_label"]),
        Paragraph("GENERATED ON", styles["scope_label"]),
        Paragraph("DATA DOMAIN", styles["scope_label"]),
    ]
    scope_value_row = [
        Paragraph(str(chart_count), styles["scope_value"]),
        Paragraph(date_str,         styles["scope_value"]),
        Paragraph(domain.upper(),   styles["scope_value"]),
    ]
    scope_table = Table(
        [scope_header_row, scope_value_row],
        colWidths=[1.6 * inch, 2.6 * inch, 2.0 * inch],
    )
    scope_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), scope_bg),
        ("TOPPADDING",    (0, 0), (-1, -1),  8),
        ("BOTTOMPADDING", (0, 0), (-1, -1),  8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ("LINEBEFORE",    (0, 0), ( 0, -1),  3, scope_bor),
        ("LINEBELOW",     (0, 0), (-1,  0),  0.4, C_RULE_SOFT),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(scope_table)
    story.append(Spacer(1, 0.3 * inch))

    # ── Key Takeaways ────────────────────────────────────────────────────────
    for el in _section_head("Key Takeaways", styles):
        story.append(el)

    for point in plan.get("key_takeaways", []):
        converted = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', point)
        t = Table(
            [[Paragraph(converted, styles["takeaway_text"])]],
            colWidths=[6.2 * inch],
        )
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("TOPPADDING",    (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ("LEFTPADDING",   (0, 0), (-1, -1), 18),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
            ("LINEBEFORE",    (0, 0), ( 0, -1),  2, C_BRAND),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.065 * inch))

    story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
# Chart pages
# ══════════════════════════════════════════════════════════════════════════════

def _chart_pages(story: list, chart_results: list,
                 narration_map: dict, styles: dict,
                 C_BRAND: colors.Color):
    """
    One chart per page.

    Layout per chart:
      Counter (right-aligned, small) + Chart title (large)
      ──────────────────────────────────────────
      [Chart image in a soft grey panel]
      INSIGHT  (uppercase label, brand color)
      ─── thin rule ───
      Narration text (justified, 10/17)
      Analysis date · Chart N of T   (right-aligned, 7.5pt, muted)
    """
    date_str = datetime.now().strftime("%B %d, %Y")
    total    = len(chart_results)

    for el in _section_head("Analysis & Charts", styles):
        story.append(el)

    for i, chart in enumerate(chart_results):
        n = i + 1

        # ── Counter + title row ──────────────────────────────────────────────
        story.append(Paragraph(f"Chart {n} / {total}", styles["chart_counter"]))
        story.append(Paragraph(chart["title"], styles["chart_title"]))
        story.append(Spacer(1, 0.08 * inch))

        # ── Chart image panel ────────────────────────────────────────────────
        img = Image(chart["png_path"], width=6.5 * inch, height=3.5 * inch)
        img_table = Table([[img]], colWidths=[6.5 * inch])
        img_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), C_BG_CARD),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            # No BOX border — clean modern look
        ]))
        story.append(img_table)
        story.append(Spacer(1, 0.14 * inch))

        # ── INSIGHT label + thin rule ────────────────────────────────────────
        story.append(Paragraph("INSIGHT", styles["insight_label"]))
        story.append(_thin_rule(color=C_BRAND, thickness=0.5,
                                 space_before=2, space_after=8))

        # ── Narration ────────────────────────────────────────────────────────
        insight = narration_map.get(chart["chart_id"], "")
        story.append(_md_to_rl(insight, styles["chart_insight"]))

        # ── Footer rule + meta line ──────────────────────────────────────────
        story.append(_thin_rule(color=C_RULE_SOFT, thickness=0.4,
                                 space_before=4, space_after=3))
        story.append(Paragraph(
            f"Analysis based on dataset processed on {date_str}  ·  "
            f"Chart {n} of {total}",
            styles["chart_footer"],
        ))

        if i < total - 1:
            story.append(PageBreak())


# ══════════════════════════════════════════════════════════════════════════════
# Client Summary page
# ══════════════════════════════════════════════════════════════════════════════

def _client_summary_page(story: list, plan: dict, styles: dict,
                          company_name: str, C_BRAND: colors.Color,
                          C_BRAND_HEX: str):
    """
    Final summary page with:
      "[Company] — Strategic Recommendations"   (branded header)
      Areas of Growth   (green accent cards)
      Areas to Focus On  (amber accent cards)
      Recommendations    (violet accent cards, numbered)
      Closing Note       (brand-tinted card)
    """
    story.append(PageBreak())

    # ── Branded header ───────────────────────────────────────────────────────
    story.append(Paragraph(
        f"{company_name} — Strategic Recommendations",
        styles["client_header"],
    ))
    story.append(_thin_rule(color=C_BRAND, thickness=1.0,
                             space_before=2, space_after=14))

    # ── Areas of Growth ──────────────────────────────────────────────────────
    for el in _section_head("Areas of Growth", styles):
        story.append(el)
    for point in plan.get("growth_areas", []):
        story.append(_left_border_card(
            point, styles["card_text"], _GROWTH_BG, _GROWTH_ACC,
        ))
        story.append(Spacer(1, 0.06 * inch))

    story.append(Spacer(1, 0.2 * inch))

    # ── Areas to Focus On ────────────────────────────────────────────────────
    for el in _section_head("Areas to Focus On", styles):
        story.append(el)
    for point in plan.get("focus_areas", []):
        story.append(_left_border_card(
            point, styles["card_text"], _FOCUS_BG, _FOCUS_ACC,
        ))
        story.append(Spacer(1, 0.06 * inch))

    story.append(Spacer(1, 0.2 * inch))

    # ── Recommendations ──────────────────────────────────────────────────────
    for el in _section_head("Recommendations", styles):
        story.append(el)
    for idx, rec in enumerate(plan.get("recommendations", []), 1):
        converted = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', rec)
        # Two-column: number | text
        num_cell  = Paragraph(f"{idx:02d}", styles["rec_num"])
        text_cell = Paragraph(converted, styles["card_text"])
        row_table = Table(
            [[num_cell, text_cell]],
            colWidths=[0.45 * inch, 5.75 * inch],
        )
        row_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), _REC_BG),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING",   (0, 0), (-1, -1), 14),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LINEBEFORE",    (0, 0), ( 0, -1),  3, _REC_ACC),
        ]))
        story.append(row_table)
        story.append(Spacer(1, 0.06 * inch))

    story.append(Spacer(1, 0.28 * inch))

    # ── Closing Note ─────────────────────────────────────────────────────────
    for el in _section_head("Closing Note", styles):
        story.append(el)

    closing_bg  = colors.HexColor(_lighten(C_BRAND_HEX, 92))
    closing_txt = plan.get("closing_summary", "")
    converted   = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', closing_txt)
    close_table = Table(
        [[Paragraph(converted, styles["closing_text"])]],
        colWidths=[6.2 * inch],
    )
    close_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), closing_bg),
        ("TOPPADDING",    (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ("LEFTPADDING",   (0, 0), (-1, -1), 20),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
        ("LINEABOVE",     (0, 0), (-1,  0),  2, C_BRAND),
    ]))
    story.append(close_table)


# ══════════════════════════════════════════════════════════════════════════════
# Public entry point
# ══════════════════════════════════════════════════════════════════════════════

def build(
    chart_results:   list,
    narrations:      list,
    plan:            dict,
    report_id:       str,
    company_name:    str = "Client",
    brand_color_hex: str = "#2563eb",
) -> str:
    """
    Assemble and write the PDF report.

    Parameters
    ----------
    chart_results    list of chart dicts from chart_engine.generate_charts()
    narrations       list of {"chart_id": ..., "insight_text": ...}
    plan             LLM plan dict (report_title, domain, exec summary, etc.)
    report_id        8-char report UUID
    company_name     client company name — appears on cover and summary header
    brand_color_hex  hex color '#rrggbb' for all decorative elements

    Returns
    -------
    str  absolute path to the generated PDF file
    """
    output_path = os.path.join(REPORTS_PATH, f"{report_id}.pdf")

    # ── Derive full brand palette ────────────────────────────────────────────
    C_BRAND       = colors.HexColor(brand_color_hex)
    brand_dark_hex = _darken(brand_color_hex, 35)

    styles        = _make_styles(C_BRAND, brand_color_hex)
    narration_map = {n["chart_id"]: n["insight_text"] for n in narrations}
    story         = []

    # ── Build story ──────────────────────────────────────────────────────────
    _cover_page(story, plan, styles, company_name, C_BRAND, brand_color_hex)
    _summary_page(story, plan, styles,
                  chart_count=len(chart_results),
                  domain=plan.get("domain", "general"),
                  C_BRAND=C_BRAND,
                  C_BRAND_HEX=brand_color_hex)
    _chart_pages(story, chart_results, narration_map, styles, C_BRAND)
    _client_summary_page(story, plan, styles,
                          company_name=company_name,
                          C_BRAND=C_BRAND,
                          C_BRAND_HEX=brand_color_hex)

    # ── Page callbacks ───────────────────────────────────────────────────────
    first_page_cb, later_pages_cb = _make_page_callbacks(brand_color_hex, [])

    # ── Build document ───────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=0.9 * inch,
        leftMargin=0.9 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.85 * inch,
    )
    doc.build(story, onFirstPage=first_page_cb, onLaterPages=later_pages_cb)

    return output_path