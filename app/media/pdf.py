"""Builds the PDFs Rafiq makes for users (evidence pack, letters, forms).

Safety:
- Every value is escaped before it reaches ReportLab's mini-markup, so text a
  user typed (an employer's name, say) can never inject tags, links or images.
- English sections use the built-in PDF fonts, so text is reduced to Latin-1
  (characters that can't be shown become "?").
- Arabic sections (Section.rtl) use the bundled DejaVu Sans (app/media/fonts,
  free licence), are shaped with arabic-reshaper and laid out right to left with
  python-bidi. Lines are wrapped BEFORE reordering so multi-line text reads in
  the right order.
- Nothing is written to disk: the PDF is built in memory and sent.
"""

from __future__ import annotations

import io
import textwrap
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

FONT_DIR = Path(__file__).parent / "fonts"

MAX_TEXT = 4000  # per paragraph, so a pasted essay can't blow up a page


def safe(text: object) -> str:
    s = str(text if text is not None else "")[:MAX_TEXT]
    s = s.encode("latin-1", "replace").decode("latin-1")
    return escape(s).replace("\n", "<br/>")


def rtl(text: object, width: int = 80) -> str:
    """Arabic (or mixed) text -> escaped, shaped, visually ordered lines joined by <br/>."""
    import arabic_reshaper
    from bidi.algorithm import get_display

    raw = str(text if text is not None else "")[:MAX_TEXT]
    lines: list[str] = []
    for para in raw.split("\n"):
        lines += textwrap.wrap(para, width) or [""]
    def one(line: str) -> str:
        if not any("\u0600" <= ch <= "\u06ff" or "\u0750" <= ch <= "\u077f" for ch in line):
            return escape(line)                       # e.g. the worker's own English words: keep left to right
        return escape(get_display(arabic_reshaper.reshape(line)))

    return "<br/>".join(one(line) for line in lines)


@lru_cache
def _arabic_fonts() -> tuple[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    pdfmetrics.registerFont(TTFont("RafiqSans", str(FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("RafiqSans-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
    return "RafiqSans", "RafiqSans-Bold"


@dataclass
class Section:
    heading: str | None = None
    paragraphs: list[str] = field(default_factory=list)
    table: list[list[str]] | None = None         # first row = header
    page_break_before: bool = False
    rtl: bool = False                            # Arabic: right to left, Unicode font
    big: bool = False                            # heading drawn as a page title


def build_pdf(title: str, subtitle: str, sections: list[Section], footer: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.5, leading=14)
    h1 = ParagraphStyle("h1", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=17, leading=21,
                        alignment=0, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=body, textColor=colors.HexColor("#555555"), fontSize=9.5)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12.5,
                        textColor=colors.HexColor("#0b5d4b"), spaceBefore=10, spaceAfter=4)
    cell = ParagraphStyle("cell", parent=body, fontSize=9.5, leading=12)
    styles_ar: dict[str, ParagraphStyle] = {}
    if any(sec.rtl for sec in sections):
        reg, bold = _arabic_fonts()
        styles_ar = {
            "body": ParagraphStyle("ar_body", parent=body, fontName=reg, fontSize=10.5, leading=16, alignment=2),
            "h1": ParagraphStyle("ar_h1", parent=h1, fontName=bold, alignment=2, leading=24),
            "h2": ParagraphStyle("ar_h2", parent=h2, fontName=bold, alignment=2),
            "cell": ParagraphStyle("ar_cell", parent=cell, fontName=reg, alignment=2, leading=14),
            "cellb": ParagraphStyle("ar_cellb", parent=cell, fontName=bold, alignment=2, leading=14),
        }

    def on_page(canvas, doc):  # type: ignore[no-untyped-def]
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(18 * mm, 10 * mm, footer.encode("latin-1", "replace").decode("latin-1")[:150])
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    flow: list = [Paragraph(safe(title), h1), Paragraph(safe(subtitle), sub), Spacer(1, 6)]
    for sec in sections:
        if sec.page_break_before:
            flow.append(PageBreak())
        if sec.rtl:
            if sec.heading:
                flow.append(Paragraph(rtl(sec.heading, 60), styles_ar["h1" if sec.big else "h2"]))
            for p in sec.paragraphs:
                flow.append(Paragraph(rtl(p, 95), styles_ar["body"]))
                flow.append(Spacer(1, 4))
            if sec.table:
                n = max(len(r) for r in sec.table)
                width = max(18, 90 // n)
                data = [[Paragraph(rtl(c, width), styles_ar["cellb" if i == 0 else "cell"]) for c in reversed(row)]
                        for i, row in enumerate(sec.table)]
                tbl = Table(data, repeatRows=1, hAlign="RIGHT")
                tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6f2ef")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b5c9c3")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]))
                flow.append(tbl)
                flow.append(Spacer(1, 6))
            continue
        if sec.heading:
            flow.append(Paragraph(safe(sec.heading), h1 if sec.big else h2))
        for p in sec.paragraphs:
            flow.append(Paragraph(safe(p), body))
            flow.append(Spacer(1, 4))
        if sec.table:
            data = [[Paragraph(("<b>%s</b>" if i == 0 else "%s") % safe(c), cell) for c in row]
                    for i, row in enumerate(sec.table)]
            tbl = Table(data, repeatRows=1, hAlign="LEFT")
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6f2ef")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b5c9c3")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            flow.append(tbl)
            flow.append(Spacer(1, 6))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=18 * mm, title=title[:80], author="Rafiq", creator="Rafiq")
    doc.build(flow, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()
