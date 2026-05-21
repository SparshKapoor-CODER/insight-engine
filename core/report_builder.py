import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from config import REPORTS_PATH

def build(chart_results: list, narrations: list, plan: dict, report_id: str) -> str:
    output_path = os.path.join(REPORTS_PATH, f"{report_id}.pdf")
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            rightMargin=inch, leftMargin=inch,
                            topMargin=inch, bottomMargin=inch)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", fontSize=22, fontName="Helvetica-Bold",
                                  spaceAfter=10, textColor=colors.HexColor("#1a1a2e"))
    heading_style = ParagraphStyle("heading", fontSize=14, fontName="Helvetica-Bold",
                                    spaceAfter=6, textColor=colors.HexColor("#16213e"))
    body_style = ParagraphStyle("body", fontSize=10, fontName="Helvetica",
                                 spaceAfter=8, leading=16)
    takeaway_style = ParagraphStyle("takeaway", fontSize=10, fontName="Helvetica",
                                     leftIndent=20, spaceAfter=4)

    narration_map = {n["chart_id"]: n["insight_text"] for n in narrations}
    story = []

    # Title
    story.append(Paragraph(plan["report_title"], title_style))
    story.append(Paragraph(f"Domain: {plan['domain'].capitalize()}", body_style))
    story.append(Spacer(1, 0.2 * inch))

    # Executive summary
    story.append(Paragraph("Executive Summary", heading_style))
    story.append(Paragraph(plan["executive_summary"], body_style))
    story.append(Spacer(1, 0.2 * inch))

    # Key takeaways
    story.append(Paragraph("Key Takeaways", heading_style))
    for point in plan["key_takeaways"]:
        story.append(Paragraph(f"• {point}", takeaway_style))
    story.append(PageBreak())

    # Charts
    for chart in chart_results:
        story.append(Paragraph(chart["title"], heading_style))
        story.append(Spacer(1, 0.1 * inch))

        img = Image(chart["png_path"], width=6 * inch, height=3 * inch)
        story.append(img)
        story.append(Spacer(1, 0.15 * inch))

        insight = narration_map.get(chart["chart_id"], "")
        story.append(Paragraph(insight, body_style))
        story.append(Spacer(1, 0.3 * inch))

    doc.build(story)
    return output_path