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
from reportlab.platypus.flowables import Flowable
from config import REPORTS_PATH

# ── Static brand colors (non-decorative / body text) ────────────────────────
C_DARK       = colors.HexColor("#0f172a")
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


# ── Hex color math helpers ───────────────────────────────────────────────────
def _hex_to_rgb(hex_str: str) -> tuple:
    """Convert '#rrggbb' → (r, g, b) as 0–255 ints."""
    h = hex_str.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert 0–255 ints → '#rrggbb'."""
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, r)),
        max(0, min(255, g)),
        max(0, min(255, b))
    )


def _darken(hex_str: str, pct: float) -> str:
    """Darken a hex color by pct percent (0–100). Pure stdlib hex math."""
    r, g, b = _hex_to_rgb(hex_str)
    factor  = 1.0 - (pct / 100.0)
    return _rgb_to_hex(int(r * factor), int(g * factor), int(b * factor))


def _lighten(hex_str: str, pct: float) -> str:
    """Lighten a hex color by pct percent (0–100). Pure stdlib hex math."""
    r, g, b = _hex_to_rgb(hex_str)
    factor  = pct / 100.0
    return _rgb_to_hex(
        int(r + (255 - r) * factor),
        int(g + (255 - g) * factor),
        int(b + (255 - b) * factor)
    )


# ── Watermark flowable ───────────────────────────────────────────────────────
class WatermarkFlowable(Flowable):
    """
    Draws a diagonal 'Insight Engine' watermark centered on the page.
    Drawn at draw-time so it sits behind content.
    """
    def __init__(self, page_width, page_height, text="Insight Engine"):
        Flowable.__init__(self)
        self.page_width  = page_width
        self.page_height = page_height
        self.text        = text
        self.width       = 0
        self.height      = 0

    def draw(self):
        canvas = self.canv
        canvas.saveState()

        # Position: center of the page
        canvas.translate(self.page_width / 2, self.page_height / 2)
        canvas.rotate(45)

        # Style: very light diagonal text
        canvas.setFont("Helvetica-Bold", 52)
        canvas.setFillColorRGB(0.85, 0.88, 0.92, alpha=0.18)  # light slate, near transparent

        # Draw text centered at origin
        canvas.drawCentredString(0, 0, self.text)

        canvas.restoreState()


# ── Watermark canvas callback (for use in onFirstPage / onLaterPages) ────────
def _make_watermark_cb(text="Insight Engine"):
    """Returns a canvas callback that draws the watermark on every page."""
    def _draw_watermark(canvas, doc):
        canvas.saveState()
        pw = doc.pagesize[0]
        ph = doc.pagesize[1]

        canvas.translate(pw / 2, ph / 2)
        canvas.rotate(45)

        canvas.setFont("Helvetica-Bold", 52)
        canvas.setFillColorRGB(0.85, 0.88, 0.92, alpha=0.15)
        canvas.drawCentredString(0, 0, text)

        canvas.restoreState()
    return _draw_watermark


# ── Style definitions ────────────────────────────────────────────────────────
def _make_styles(C_BRAND: colors.Color, C_COVER_BG: colors.Color):
    """
    Build and return all ParagraphStyles.
    C_BRAND and C_COVER_BG are derived from brand_color_hex at build() time.
    Signature unchanged — _make_styles() is called only from build().
    """
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
    cover_meta = ParagraphStyle(
        "cover_meta",
        fontSize=10, fontName="Helvetica",
        textColor=colors.HexColor("#cbd5e1"), spaceAfter=4, leading=16
    )
    cover_confidential = ParagraphStyle(
        "cover_confidential",
        fontSize=8, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#94a3b8"),
        spaceAfter=0, leading=12,
        letterSpacing=1.2
    )
    section_heading = ParagraphStyle(
        "section_heading",
        fontSize=14, fontName="Helvetica-Bold",
        textColor=C_BRAND, spaceAfter=6, spaceBefore=4
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
    chart_footer = ParagraphStyle(
        "chart_footer",
        fontSize=8, fontName="Helvetica",
        textColor=colors.HexColor("#64748b"),  # muted slate gray
        spaceAfter=4, leading=12
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
    scope_label = ParagraphStyle(
        "scope_label",
        fontSize=8, fontName="Helvetica-Bold",
        textColor=C_SECONDARY, spaceAfter=2,
        letterSpacing=0.8
    )
    scope_value = ParagraphStyle(
        "scope_value",
        fontSize=10, fontName="Helvetica",
        textColor=C_DARK, spaceAfter=0, leading=14
    )

    return {
        "cover_title":        cover_title,
        "cover_sub":          cover_sub,
        "cover_meta":         cover_meta,
        "cover_confidential": cover_confidential,
        "section_heading":    section_heading,
        "body":               body,
        "chart_title":        chart_title,
        "chart_insight":      chart_insight,
        "chart_footer":       chart_footer,
        "page_label":         page_label,
        "closing":            closing,
        "scope_label":        scope_label,
        "scope_value":        scope_value,
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
def _cover_page(story: list, plan: dict, styles: dict,
                company_name: str, C_BRAND: colors.Color,
                C_COVER_BG: colors.Color, C_COVER_DARK: colors.Color):
    """
    Two-section cover layout:
      Top    — company name in large white text on a dark background
               derived from brand_color_hex darkened by 30%
      Bottom — report title, 'Prepared by Insight Engine', generation date
      Footer — confidentiality line
    All colors derive from brand_color_hex, not hardcoded blue.
    """
    date_str = datetime.now().strftime("%B %d, %Y")

    # ── Top section: company name on dark brand background ──────────────────
    top_data = [[Paragraph(company_name, styles["cover_title"])]]
    top_table = Table(top_data, colWidths=[6.5 * inch])
    top_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_COVER_DARK),
        ("LEFTPADDING",   (0, 0), (-1, -1), 32),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 32),
        ("TOPPADDING",    (0, 0), (-1, -1), 40),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 40),
    ]))

    # ── Bottom section: title + prepared-by + date ───────────────────────────
    prepared_style = ParagraphStyle(
        "cover_prepared",
        fontSize=10, fontName="Helvetica",
        textColor=C_BRAND, spaceAfter=4, leading=16
    )
    title_display_style = ParagraphStyle(
        "cover_title_display",
        fontSize=16, fontName="Helvetica-Bold",
        textColor=C_DARK, spaceAfter=10, leading=22
    )
    bottom_content = [
        Paragraph(plan["report_title"], title_display_style),
        Paragraph("Prepared by Insight Engine", prepared_style),
        Paragraph(f"Generated: {date_str}", styles["cover_meta"]),
    ]
    bottom_data = [[cell] for cell in bottom_content]
    bottom_table = Table(
        [[item] for item in bottom_content],
        colWidths=[6.5 * inch]
    )
    bottom_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("LEFTPADDING",   (0, 0), (-1, -1), 32),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 32),
        ("TOPPADDING",    (0, 0), (-1, -1), 24),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 24),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
    ]))

    # ── Domain pill ───────────────────────────────────────────────────────────
    domain_style = ParagraphStyle(
        "cover_domain",
        fontSize=9, fontName="Helvetica-Bold",
        textColor=C_WHITE, spaceAfter=0, leading=14,
        letterSpacing=1.5
    )

    story.append(Spacer(1, 0.6 * inch))
    story.append(top_table)
    story.append(bottom_table)
    story.append(Spacer(1, 0.15 * inch))

    # Domain badge
    domain_data = [[Paragraph(plan["domain"].upper(), domain_style)]]
    domain_table = Table(domain_data, colWidths=[6.5 * inch])
    domain_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_BRAND),
        ("LEFTPADDING",   (0, 0), (-1, -1), 32),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 32),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(domain_table)
    story.append(Spacer(1, 0.3 * inch))

    # ── Confidentiality line ─────────────────────────────────────────────────
    story.append(Paragraph(
        f"CONFIDENTIAL — Prepared exclusively for {company_name}",
        styles["cover_confidential"]
    ))
    story.append(PageBreak())


# ── Summary page (exec summary + takeaways) ───────────────────────────────────
def _summary_page(story: list, plan: dict, styles: dict,
                  chart_count: int, domain: str,
                  C_BRAND: colors.Color, C_BRAND_HEX: str):
    """
    Executive summary section.

    Developer note — executive_summary field expectations:
      - Maximum 5 sentences
      - No generic filler ("This report analyzes…", "The data shows…")
      - Should open with the single most important finding
      - Should close with a forward-looking implication
      - Tone: senior management consulting, direct and data-driven

    Below the summary: a 'Report Scope' metadata box showing
    chart count, generation date, and data domain.
    The scope box border uses brand_color_hex.
    """
    date_str = datetime.now().strftime("%B %d, %Y")

    story.append(Paragraph("Executive Summary", styles["section_heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_DIVIDER, spaceAfter=8))
    story.append(_md_to_rl(plan["executive_summary"], styles["body"]))
    story.append(Spacer(1, 0.2 * inch))

    # ── Report Scope metadata box ────────────────────────────────────────────
    scope_border = colors.HexColor(C_BRAND_HEX)
    scope_bg     = colors.HexColor("#f8fafc")

    scope_rows = [
        [
            Paragraph("CHARTS GENERATED", styles["scope_label"]),
            Paragraph("GENERATION DATE", styles["scope_label"]),
            Paragraph("DATA DOMAIN", styles["scope_label"]),
        ],
        [
            Paragraph(str(chart_count), styles["scope_value"]),
            Paragraph(date_str,         styles["scope_value"]),
            Paragraph(domain.upper(),   styles["scope_value"]),
        ],
    ]
    scope_table = Table(scope_rows, colWidths=[2.0 * inch, 2.5 * inch, 1.7 * inch])
    scope_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), scope_bg),
        ("BOX",           (0, 0), (-1, -1), 1.0, scope_border),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.5, C_DIVIDER),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(scope_table)
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("Key Takeaways", styles["section_heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_DIVIDER, spaceAfter=8))
    for point in plan.get("key_takeaways", []):
        story.append(_callout_box(point, styles["body"], C_LIGHT_BG, C_BORDER, "→  "))
        story.append(Spacer(1, 0.07 * inch))

    story.append(PageBreak())


# ── One chart per page ────────────────────────────────────────────────────────
def _chart_pages(story: list, chart_results: list,
                 narration_map: dict, styles: dict, C_BRAND: colors.Color):
    """
    Each chart page includes:
    - Chart number / title
    - Full-width chart image
    - 'Insight' heading (styled with C_BRAND instead of hardcoded C_PRIMARY)
    - Narration text
    - Footer: "Analysis based on dataset processed on [date]. Chart [n] of [total]."
      in 8pt muted slate gray font
    """
    date_str = datetime.now().strftime("%B %d, %Y")
    total    = len(chart_results)

    story.append(Paragraph("Analysis & Charts", styles["section_heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=C_DIVIDER, spaceAfter=10))

    for i, chart in enumerate(chart_results):
        n = i + 1
        story.append(Paragraph(f"Chart {n} of {total}", styles["page_label"]))
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

        # 'Insight' heading uses C_BRAND (dynamic brand color)
        insight_heading_style = ParagraphStyle(
            f"insight_heading_{n}",
            fontSize=14, fontName="Helvetica-Bold",
            textColor=C_BRAND, spaceAfter=6, spaceBefore=4
        )
        story.append(Paragraph("Insight", insight_heading_style))
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=C_DIVIDER, spaceAfter=6))
        insight = narration_map.get(chart["chart_id"], "")
        story.append(_md_to_rl(insight, styles["chart_insight"]))

        # ── Footer line ──────────────────────────────────────────────────────
        footer_text = (
            f"Analysis based on dataset processed on {date_str}. "
            f"Chart {n} of {total}."
        )
        story.append(Paragraph(footer_text, styles["chart_footer"]))

        if i < total - 1:
            story.append(PageBreak())


# ── Final client summary page ─────────────────────────────────────────────────
def _client_summary_page(story: list, plan: dict, styles: dict,
                         company_name: str, C_BRAND: colors.Color,
                         C_BRAND_HEX: str):
    """
    Client summary with:
    - Branded header: "[company_name] — Strategic Recommendations" in C_BRAND
    - Growth / Focus / Recommendations callout boxes (unchanged)
    - Closing note box border uses C_BRAND instead of hardcoded blue
    """
    story.append(PageBreak())

    # ── Branded header ───────────────────────────────────────────────────────
    header_style = ParagraphStyle(
        "client_summary_header",
        fontSize=18, fontName="Helvetica-Bold",
        textColor=C_BRAND, spaceAfter=4, leading=24
    )
    story.append(Paragraph(
        f"{company_name} — Strategic Recommendations",
        header_style
    ))
    story.append(HRFlowable(width="100%", thickness=2,
                             color=C_BRAND, spaceAfter=12))

    story.append(Paragraph("Areas of Growth", styles["section_heading"]))
    for point in plan.get("growth_areas", []):
        story.append(_callout_box(point, styles["body"],
                                  C_GREEN_BG, C_GREEN_BOR, "📈  "))
        story.append(Spacer(1, 0.07 * inch))

    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("Areas to Focus On", styles["section_heading"]))
    for point in plan.get("focus_areas", []):
        story.append(_callout_box(point, styles["body"],
                                  C_ORANGE_BG, C_ORANGE_BOR, "⚠️  "))
        story.append(Spacer(1, 0.07 * inch))

    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph("Recommendations", styles["section_heading"]))
    for i, rec in enumerate(plan.get("recommendations", []), 1):
        story.append(_callout_box(rec, styles["body"],
                                  C_PURPLE_BG, C_PURPLE_BOR, f"{i}.  "))
        story.append(Spacer(1, 0.07 * inch))

    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("Closing Note", styles["section_heading"]))
    story.append(HRFlowable(width="100%", thickness=1,
                             color=C_DIVIDER, spaceAfter=8))
    closing_text  = plan.get("closing_summary", "")
    closing_style = ParagraphStyle(
        "closing_inner",
        fontSize=10, fontName="Helvetica",
        textColor=colors.HexColor("#1e3a5f"),
        leading=18, spaceAfter=0
    )
    # Closing note border uses C_BRAND (dynamic)
    closing_border = colors.HexColor(C_BRAND_HEX)
    closing_light  = colors.HexColor(_lighten(C_BRAND_HEX, 90))
    story.append(_callout_box(
        closing_text, closing_style,
        closing_light, closing_border
    ))


# ── DB persistence helper ────────────────────────────────────────────────────
def store_pdf_in_db(report_id: str, pdf_path: str) -> None:
    """
    Read the PDF from disk and store it as a BLOB on the matching Report row.
    Deferred import to avoid circular imports at module load time.
    """
    try:
        from models.database import db, Report
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        report = Report.query.get(report_id)
        if report:
            report.pdf_data = pdf_bytes
            db.session.commit()
    except Exception as e:
        print(f"WARNING: Could not store PDF BLOB for {report_id}: {e}")


# ── Main build ────────────────────────────────────────────────────────────────
def build(
    chart_results: list,
    narrations:    list,
    plan:          dict,
    report_id:     str,
    company_name:  str = "Client",
    brand_color_hex: str = "#2563eb",
) -> str:
    """
    Assemble and write the PDF report.

    New parameters (both optional, callers not providing them get defaults):
      company_name      (str) — client name shown on cover and summary header
      brand_color_hex   (str) — hex color '#rrggbb' used for all decorative
                                elements (cover, headings, borders, insight
                                section colors). Defaults to Insight Engine blue.

    Changed function signatures vs. previous version:
      - build() now accepts company_name and brand_color_hex (optional)
      - _make_styles() now accepts C_BRAND and C_COVER_BG (internal only)
      - _cover_page(), _summary_page(), _chart_pages(), _client_summary_page()
        now accept brand color arguments (internal only)

    Callers that previously called build(charts, stories, plan, report_id)
    continue to work unchanged (new params default gracefully).
    """
    output_path = os.path.join(REPORTS_PATH, f"{report_id}.pdf")

    # ── Derive all dynamic brand colors at the top of build() ───────────────
    # C_BRAND      — the primary brand color (decorative elements)
    # C_COVER_DARK — brand color darkened 30% (cover top section background)
    # C_COVER_BG   — retained as alias for cover_dark for style compat
    C_BRAND      = colors.HexColor(brand_color_hex)
    cover_dark_hex = _darken(brand_color_hex, 30)
    C_COVER_DARK = colors.HexColor(cover_dark_hex)
    C_COVER_BG   = C_COVER_DARK   # used by closing style for border compat

    styles        = _make_styles(C_BRAND, C_COVER_BG)
    narration_map = {n["chart_id"]: n["insight_text"] for n in narrations}
    story         = []

    # ── Watermark canvas callback ─────────────────────────────────────────────
    watermark_cb = _make_watermark_cb("Insight Engine")

    _cover_page(story, plan, styles, company_name,
                C_BRAND, C_COVER_BG, C_COVER_DARK)

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

    # ── Build document with watermark on every page ──────────────────────────
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        rightMargin=inch, leftMargin=inch,
        topMargin=0.8 * inch, bottomMargin=0.8 * inch
    )

    doc.build(
        story,
        onFirstPage=watermark_cb,
        onLaterPages=watermark_cb,
    )

    store_pdf_in_db(report_id, output_path)

    return output_path