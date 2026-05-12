#!/usr/bin/env python3
"""
Branded PDF report generator for competitor analysis.
Reads .tmp/competitor_research.json + business_profile.yaml,
produces a styled PDF at .tmp/<company_slug>_competitor_analysis_YYYY-MM-DD.pdf.
Brand colors, logo, and company name are all read from business_profile.yaml.
"""

import json
import sys
import argparse
from datetime import date
from pathlib import Path

import yaml
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    PageBreak,
    KeepTogether,
    Image,
)
from reportlab.platypus.flowables import Flowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

ROOT = Path(__file__).parent.parent
TMP = ROOT / ".tmp"


def load_brand_colors(profile: dict) -> dict:
    """Extract brand colors from business_profile.yaml, with sensible defaults."""
    brand_colors = profile.get("brand", {}).get("colors", {})
    return {
        "C_BG":      colors.HexColor(brand_colors.get("background",      "#0a0a0a")),
        "C_SURFACE": colors.HexColor(brand_colors.get("surface",         "#0d0d0d")),
        "C_BORDER":  colors.HexColor(brand_colors.get("border",          "#2a2a2a")),
        "C_WHITE":   colors.HexColor(brand_colors.get("foreground",      "#ffffff")),
        "C_MUTED":   colors.HexColor(brand_colors.get("muted",           "#9ca3af")),
        "C_ACCENT":  colors.HexColor(brand_colors.get("primary_accent",  "#4a6cf7")),
        "C_EMERALD": colors.HexColor(brand_colors.get("emerald",         "#00d294")),
        "C_AMBER":   colors.HexColor(brand_colors.get("amber",           "#f99c00")),
        "C_BLUE":    colors.HexColor(brand_colors.get("blue",            "#54a2ff")),
    }


# Module-level color vars — overwritten in main() once profile is loaded
C_BG = colors.HexColor("#0a0a0a")
C_SURFACE = colors.HexColor("#0d0d0d")
C_BORDER = colors.HexColor("#2a2a2a")
C_WHITE = colors.HexColor("#ffffff")
C_MUTED = colors.HexColor("#9ca3af")
C_ACCENT = colors.HexColor("#4a6cf7")
C_EMERALD = colors.HexColor("#00d294")
C_AMBER = colors.HexColor("#f99c00")
C_BLUE = colors.HexColor("#54a2ff")

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


def get_styles():
    """Build the complete style sheet for the report."""
    base = getSampleStyleSheet()

    def s(name, **kwargs):
        return ParagraphStyle(name, **kwargs)

    return {
        "cover_title": s("cover_title",
            fontName="Helvetica-Bold", fontSize=32, textColor=C_WHITE,
            leading=38, alignment=TA_LEFT, spaceAfter=8),
        "cover_subtitle": s("cover_subtitle",
            fontName="Helvetica", fontSize=14, textColor=C_MUTED,
            leading=20, alignment=TA_LEFT, spaceAfter=6),
        "cover_date": s("cover_date",
            fontName="Helvetica", fontSize=11, textColor=C_MUTED,
            alignment=TA_LEFT),
        "section_header": s("section_header",
            fontName="Helvetica-Bold", fontSize=18, textColor=C_ACCENT,
            leading=24, spaceBefore=18, spaceAfter=10),
        "subsection_header": s("subsection_header",
            fontName="Helvetica-Bold", fontSize=13, textColor=C_WHITE,
            leading=18, spaceBefore=12, spaceAfter=6),
        "body": s("body",
            fontName="Helvetica", fontSize=10, textColor=C_WHITE,
            leading=16, spaceAfter=6),
        "body_muted": s("body_muted",
            fontName="Helvetica", fontSize=10, textColor=C_MUTED,
            leading=16, spaceAfter=4),
        "bullet": s("bullet",
            fontName="Helvetica", fontSize=10, textColor=C_WHITE,
            leading=16, leftIndent=14, spaceAfter=4,
            bulletFontName="Helvetica", bulletFontSize=10, bulletColor=C_ACCENT),
        "label": s("label",
            fontName="Helvetica-Bold", fontSize=9, textColor=C_ACCENT,
            leading=12, spaceAfter=2),
        "tag_high": s("tag_high",
            fontName="Helvetica-Bold", fontSize=9, textColor=C_ACCENT, leading=12),
        "tag_medium": s("tag_medium",
            fontName="Helvetica-Bold", fontSize=9, textColor=C_AMBER, leading=12),
        "tag_low": s("tag_low",
            fontName="Helvetica-Bold", fontSize=9, textColor=C_EMERALD, leading=12),
        "table_header": s("table_header",
            fontName="Helvetica-Bold", fontSize=9, textColor=C_WHITE,
            alignment=TA_LEFT, leading=12),
        "table_cell": s("table_cell",
            fontName="Helvetica", fontSize=9, textColor=C_WHITE,
            alignment=TA_LEFT, leading=13),
        "table_cell_muted": s("table_cell_muted",
            fontName="Helvetica", fontSize=9, textColor=C_MUTED,
            alignment=TA_LEFT, leading=13),
    }


def _get_logo_png_path(profile: dict) -> Path:
    """Resolve logo PNG path from profile, relative to project root."""
    png_path = profile.get("brand", {}).get("logo", {}).get("png_path", "")
    if png_path:
        p = Path(png_path)
        if not p.is_absolute():
            p = ROOT / p
        return p
    return TMP / "logo.png"


def _logo_image(logo_png_path: Path, target_height: float):
    """Return a reportlab Image for the logo PNG, or None if not found."""
    if logo_png_path.exists():
        try:
            img = Image(str(logo_png_path), height=target_height)
            img.hAlign = "LEFT"
            return img
        except Exception:
            pass
    return None


def _draw_logo_on_canvas(canvas, x: float, y: float, height: float, logo_png_path: Path, company_name: str):
    """Draw logo directly onto a canvas at (x,y). Uses PNG if available, else draws company name."""
    if logo_png_path.exists():
        try:
            from reportlab.lib.utils import ImageReader
            from PIL import Image as PILImage
            pil_img = PILImage.open(str(logo_png_path))
            aspect = pil_img.width / pil_img.height
            w = height * aspect
            canvas.drawImage(ImageReader(str(logo_png_path)), x, y, width=w, height=height, mask="auto")
            return
        except Exception:
            pass
    # Text fallback: render company name in accent color
    canvas.saveState()
    canvas.setFillColor(C_ACCENT)
    canvas.setFont("Helvetica-Bold", height * 0.7)
    canvas.drawString(x, y + height * 0.15, company_name.lower() + ".")
    canvas.restoreState()


class CompanyLogo(Flowable):
    """Renders the company logo — uses PNG file if available, otherwise draws company name."""
    def __init__(self, size=36, logo_png_path: Path = None, company_name: str = "company"):
        super().__init__()
        self.size = size
        self.company_name = company_name
        self.logo_png_path = logo_png_path or TMP / "logo.png"
        self._img = _logo_image(self.logo_png_path, size)
        if self._img:
            self.width = self._img.imageWidth * (size / self._img.imageHeight) if hasattr(self._img, "imageHeight") and self._img.imageHeight else size * 4
            self.height = size
        else:
            self.width = size * 4
            self.height = size

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        if self._img:
            self._img.drawOn(self.canv, 0, 0)
        else:
            _draw_logo_on_canvas(self.canv, 0, 0, self.size, self.logo_png_path, self.company_name)


def make_page_template(doc, styles, logo_png_path: Path, company_name: str):
    """Create page templates with dark background and header/footer."""

    def on_cover_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(C_BG)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        canvas.setFillColor(C_ACCENT)
        canvas.rect(0, 0, 3, PAGE_H, fill=1, stroke=0)
        canvas.restoreState()

    def on_content_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(C_BG)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        canvas.setFillColor(C_ACCENT)
        canvas.rect(0, 0, 3, PAGE_H, fill=1, stroke=0)
        canvas.setStrokeColor(C_BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, PAGE_H - 14 * mm, PAGE_W - MARGIN, PAGE_H - 14 * mm)
        _draw_logo_on_canvas(canvas, MARGIN, PAGE_H - 12 * mm, 6 * mm, logo_png_path, company_name)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(C_MUTED)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 10 * mm, "Competitor Analysis Report")
        canvas.setStrokeColor(C_BORDER)
        canvas.line(MARGIN, 12 * mm, PAGE_W - MARGIN, 12 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(C_MUTED)
        canvas.drawString(MARGIN, 8 * mm, f"Generated {date.today().strftime('%B %d, %Y')} · Confidential")
        canvas.drawRightString(PAGE_W - MARGIN, 8 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    cover_frame = Frame(MARGIN, MARGIN, CONTENT_W, PAGE_H - 2 * MARGIN, id="cover")
    content_frame = Frame(MARGIN, 16 * mm, CONTENT_W, PAGE_H - 30 * mm, id="content")

    return [
        PageTemplate(id="cover", frames=[cover_frame], onPage=on_cover_page),
        PageTemplate(id="content", frames=[content_frame], onPage=on_content_page),
    ]


def threat_style(level: str, styles: dict) -> ParagraphStyle:
    mapping = {"High": "tag_high", "Medium": "tag_medium", "Low": "tag_low"}
    return styles.get(mapping.get(level, "body_muted"))


def build_cover(research: dict, styles: dict, logo_png_path: Path, company_name: str) -> list:
    company = research["company"]
    report_date = date.today().strftime("%B %d, %Y")
    meta = research.get("metadata", {})
    n = meta.get("total_competitors_analyzed", "—")

    story = [
        Spacer(1, 60 * mm),
        CompanyLogo(size=36, logo_png_path=logo_png_path, company_name=company_name),
        Spacer(1, 16 * mm),
        Paragraph("Competitor Analysis Report", styles["cover_title"]),
        Paragraph(company.get("tagline", ""), styles["cover_subtitle"]),
        Spacer(1, 6 * mm),
        HRFlowable(width=CONTENT_W, thickness=0.5, color=C_BORDER),
        Spacer(1, 6 * mm),
        Paragraph(f"Date: {report_date}", styles["cover_date"]),
        Paragraph(f"Competitors analyzed: {n}", styles["cover_date"]),
        Paragraph("Classification: Confidential", styles["cover_date"]),
        PageBreak(),
    ]
    return story


def build_exec_summary(research: dict, styles: dict) -> list:
    summary_text = research.get("executive_summary", "No summary available.")
    story = [
        Paragraph("Executive Summary", styles["section_header"]),
        HRFlowable(width=CONTENT_W, thickness=0.5, color=C_BORDER, spaceAfter=10),
    ]
    for line in summary_text.split("\n"):
        line = line.strip()
        if line.startswith("•"):
            story.append(Paragraph(line, styles["bullet"]))
        elif line:
            story.append(Paragraph(line, styles["body"]))
    story.append(Spacer(1, 8 * mm))
    return story


def build_landscape_table(profiles: list, styles: dict) -> list:
    story = [
        Paragraph("Competitive Landscape Overview", styles["section_header"]),
        HRFlowable(width=CONTENT_W, thickness=0.5, color=C_BORDER, spaceAfter=10),
    ]

    headers = ["Company", "Category", "Target Market", "Threat"]
    col_widths = [CONTENT_W * 0.22, CONTENT_W * 0.22, CONTENT_W * 0.38, CONTENT_W * 0.18]

    rows = [[Paragraph(h, styles["table_header"]) for h in headers]]
    for p in profiles:
        threat = p.get("threat_level", "—")
        threat_para = Paragraph(threat, threat_style(threat, styles))
        rows.append([
            Paragraph(p.get("name", ""), styles["table_cell"]),
            Paragraph(p.get("category", "").replace("_", " ").title(), styles["table_cell_muted"]),
            Paragraph(p.get("target_market", "—")[:120], styles["table_cell"]),
            threat_para,
        ])

    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_SURFACE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_BG, C_SURFACE]),
        ("GRID", (0, 0), (-1, -1), 0.4, C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 8 * mm))
    return story


def build_competitor_deep_dives(profiles: list, styles: dict) -> list:
    story = [
        Paragraph("Competitor Deep Dives", styles["section_header"]),
        HRFlowable(width=CONTENT_W, thickness=0.5, color=C_BORDER, spaceAfter=10),
    ]

    for p in profiles:
        name = p.get("name", "Unknown")
        threat = p.get("threat_level", "—")
        threat_label = f"Threat: {threat}"

        block = [
            Paragraph(name, styles["subsection_header"]),
            Paragraph(threat_label, threat_style(threat, styles)),
            Spacer(1, 3),
            Paragraph(p.get("overview", ""), styles["body"]),
        ]

        if p.get("products_services"):
            block.append(Paragraph("Products / Services", styles["label"]))
            for item in p["products_services"]:
                block.append(Paragraph(f"• {item}", styles["bullet"]))

        block.append(Paragraph("Pricing", styles["label"]))
        block.append(Paragraph(p.get("pricing", "Not publicly available"), styles["body_muted"]))

        if p.get("strengths"):
            block.append(Paragraph(f"Strengths vs. {p.get('_our_company', 'Us')}", styles["label"]))
            for item in p["strengths"]:
                block.append(Paragraph(f"• {item}", styles["bullet"]))

        if p.get("weaknesses"):
            block.append(Paragraph(f"Weaknesses vs. {p.get('_our_company', 'Us')}", styles["label"]))
            for item in p["weaknesses"]:
                block.append(Paragraph(f"• {item}", styles["bullet"]))

        if p.get("recent_news"):
            block.append(Paragraph("Recent Developments", styles["label"]))
            for item in p["recent_news"]:
                block.append(Paragraph(f"• {item}", styles["bullet"]))

        if p.get("threat_rationale"):
            block.append(Paragraph("Threat Rationale", styles["label"]))
            block.append(Paragraph(p["threat_rationale"], styles["body_muted"]))

        block.append(HRFlowable(width=CONTENT_W, thickness=0.3, color=C_BORDER, spaceAfter=8))
        story.append(KeepTogether(block[:6]))
        story.extend(block[6:])

    return story


def build_comparison_table(profiles: list, styles: dict) -> list:
    story = [
        Paragraph("Product / Service Comparison", styles["section_header"]),
        HRFlowable(width=CONTENT_W, thickness=0.5, color=C_BORDER, spaceAfter=10),
    ]

    dimensions = [
        "Pre-trade scoring / evaluation",
        "On-chain performance registry",
        "Strategy backtesting / simulation",
        "Agent marketplace",
        "Live production agent",
        "API-first / machine-readable",
        "Cross-chain support",
    ]

    merced_capabilities = {
        "Pre-trade scoring / evaluation": "Yes (Evaluate API)",
        "On-chain performance registry": "Yes (Verify / ERC-8004)",
        "Strategy backtesting / simulation": "Yes (Simulate sandbox)",
        "Agent marketplace": "Yes (ERC-8004 marketplace)",
        "Live production agent": "Yes (Merced Pro)",
        "API-first / machine-readable": "Yes",
        "Cross-chain support": "Yes",
    }

    top_competitors = profiles[:5]
    col_names = ["Capability", "Merced"] + [p.get("name", "—") for p in top_competitors]
    col_count = len(col_names)
    col_w = CONTENT_W / col_count

    rows = [[Paragraph(h, styles["table_header"]) for h in col_names]]
    for dim in dimensions:
        row = [Paragraph(dim, styles["table_cell"])]
        merced_val = merced_capabilities.get(dim, "—")
        row.append(Paragraph(merced_val, styles["table_cell"]))
        for p in top_competitors:
            products_text = " ".join(p.get("products_services", [])).lower()
            overview_text = p.get("overview", "").lower()
            combined = products_text + " " + overview_text
            dim_lower = dim.lower()
            keywords = dim_lower.split("/")
            has_it = any(kw.strip() in combined for kw in keywords)
            row.append(Paragraph("Partial" if has_it else "—", styles["table_cell_muted"]))
        rows.append(row)

    tbl = Table(rows, colWidths=[col_w] * col_count, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_SURFACE),
        ("BACKGROUND", (1, 1), (1, -1), colors.HexColor("#0f1a14")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_BG, C_SURFACE]),
        ("GRID", (0, 0), (-1, -1), 0.4, C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 8 * mm))
    return story


def build_pricing_section(profiles: list, styles: dict) -> list:
    story = [
        Paragraph("Pricing Intelligence", styles["section_header"]),
        HRFlowable(width=CONTENT_W, thickness=0.5, color=C_BORDER, spaceAfter=10),
    ]

    rows = [[
        Paragraph("Company", styles["table_header"]),
        Paragraph("Pricing Model", styles["table_header"]),
    ]]
    col_widths = [CONTENT_W * 0.28, CONTENT_W * 0.72]

    for p in profiles:
        rows.append([
            Paragraph(p.get("name", ""), styles["table_cell"]),
            Paragraph(p.get("pricing", "Not publicly available"), styles["table_cell_muted"]),
        ])

    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_SURFACE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_BG, C_SURFACE]),
        ("GRID", (0, 0), (-1, -1), 0.4, C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 8 * mm))
    return story


def build_strategic_gaps(gaps: list, styles: dict) -> list:
    story = [
        Paragraph("Strategic Gaps & Recommendations", styles["section_header"]),
        HRFlowable(width=CONTENT_W, thickness=0.5, color=C_BORDER, spaceAfter=10),
        Paragraph(
            "Areas where competitors are winning that Merced should address, ranked by impact.",
            styles["body_muted"],
        ),
        Spacer(1, 6),
    ]

    for i, gap in enumerate(gaps, 1):
        impact = gap.get("impact", "—")
        block = [
            Paragraph(f"{i}. {gap.get('title', 'Untitled')}", styles["subsection_header"]),
            Paragraph(f"Impact: {impact}  ·  {gap.get('timeframe', '—')}", threat_style(impact, styles)),
            Spacer(1, 3),
            Paragraph(gap.get("description", ""), styles["body"]),
        ]
        if gap.get("competitors_winning_here"):
            block.append(Paragraph("Competitors leading here:", styles["label"]))
            block.append(Paragraph(", ".join(gap["competitors_winning_here"]), styles["body_muted"]))
        if gap.get("recommended_action"):
            block.append(Paragraph("Recommended action:", styles["label"]))
            block.append(Paragraph(gap["recommended_action"], styles["body"]))
        block.append(Spacer(1, 6))
        story.extend(block)

    return story


def main():
    parser = argparse.ArgumentParser(description="Generate Merced branded competitor analysis PDF")
    parser.add_argument(
        "--research",
        default=str(TMP / "competitor_research.json"),
        help="Path to competitor_research.json",
    )
    parser.add_argument(
        "--profile",
        default=str(ROOT / "business_profile.yaml"),
        help="Path to business_profile.yaml",
    )
    parser.add_argument(
        "--output",
        default=str(TMP / f"merced_competitor_analysis_{date.today().isoformat()}.pdf"),
        help="Output PDF path",
    )
    args = parser.parse_args()

    with open(args.research) as f:
        research = json.load(f)
    with open(args.profile) as f:
        profile = yaml.safe_load(f)

    styles = get_styles()
    profiles = research.get("competitor_profiles", [])
    gaps = research.get("strategic_gaps", [])

    doc = BaseDocTemplate(
        args.output,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )
    doc.addPageTemplates(make_page_template(doc, styles))

    story = []
    story += build_cover(research, styles)

    # Switch to content template after cover
    from reportlab.platypus import NextPageTemplate
    story.append(NextPageTemplate("content"))

    story += build_exec_summary(research, styles)
    story.append(PageBreak())
    story += build_landscape_table(profiles, styles)
    story.append(PageBreak())
    story += build_competitor_deep_dives(profiles, styles)
    story.append(PageBreak())
    story += build_comparison_table(profiles, styles)
    story.append(PageBreak())
    story += build_pricing_section(profiles, styles)
    story.append(PageBreak())
    story += build_strategic_gaps(gaps, styles)

    doc.build(story)
    print(f"PDF generated: {args.output}")
    return args.output


if __name__ == "__main__":
    main()
