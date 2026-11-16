# ruff: noqa: E501
"""ReportLab PDF generation for WEB-06 reports."""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    Image,
    LongTable,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from .reporting import ReportSnapshot

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS = PROJECT_ROOT / "frontend" / "public" / "assets"
LOGO = ASSETS / "segyrcalc-logo.png"
FONT_REGULAR = ASSETS / "fonts" / "NotoSans-Regular.ttf"
FONT_BOLD = ASSETS / "fonts" / "NotoSans-Bold.ttf"
FONT_FALLBACK_REGULAR = ASSETS / "fonts" / "Vera.ttf"
FONT_FALLBACK_BOLD = ASSETS / "fonts" / "VeraBd.ttf"
_FALLBACK_REGULAR = "SegyrcFallback"
_FALLBACK_BOLD = "SegyrcFallbackBold"
_FONT_CMAPS: dict[str, dict[int, int]] = {}
NAVY = colors.HexColor("#13263E")
RED = colors.HexColor("#B52432")
LIGHT = colors.HexColor("#F2F5F8")
BORDER = colors.HexColor("#D5DEE8")
MUTED = colors.HexColor("#5D6B7A")
WHITE = colors.white


def _register_fonts() -> tuple[str, str]:
    regular = "Helvetica"
    bold = "Helvetica-Bold"
    if FONT_REGULAR.is_file() and FONT_BOLD.is_file():
        try:
            pdfmetrics.registerFont(TTFont("SegyrcRegular", str(FONT_REGULAR)))
            pdfmetrics.registerFont(TTFont("SegyrcBold", str(FONT_BOLD)))
            regular = "SegyrcRegular"
            bold = "SegyrcBold"
        except Exception:
            pass
    for name, path in (
        (_FALLBACK_REGULAR, FONT_FALLBACK_REGULAR),
        (_FALLBACK_BOLD, FONT_FALLBACK_BOLD),
    ):
        if not path.is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont(name, str(path)))
            _FONT_CMAPS[name] = pdfmetrics.getFont(name).face.charToGlyph
        except Exception:
            continue
    return regular, bold


def _font_cmap(name: str) -> dict[int, int]:
    if name in _FONT_CMAPS:
        return _FONT_CMAPS[name]
    try:
        face = getattr(pdfmetrics.getFont(name), "face", None)
        cmap = getattr(face, "charToGlyph", None)
        if cmap:
            _FONT_CMAPS[name] = cmap
            return cmap
    except Exception:
        pass
    return {}


def _escape(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _xml(value: object) -> str:
    return _escape(value)


def _markup(value: object, primary: str, fallback: str) -> str:
    """Escape text and mark glyphs absent from the primary PDF font.

    ReportLab does not fall back between fonts. Wrapping only the missing
    glyphs in an inline ``font`` tag lets the PDF use the bundled Vera font for
    mathematical symbols while keeping Noto Sans for the rest of the text.
    """
    text = "" if value is None else str(value)
    primary_cmap = _font_cmap(primary)
    fallback_cmap = _font_cmap(fallback)
    if not primary_cmap or not fallback_cmap:
        return _escape(text)

    parts: list[str] = []
    run: list[str] = []
    in_fallback = False

    def flush() -> None:
        nonlocal run
        if not run:
            return
        escaped = "".join(_escape(ch) for ch in run)
        if in_fallback:
            parts.append(f'<font name="{fallback}">{escaped}</font>')
        else:
            parts.append(escaped)
        run = []

    for char in text:
        needs_fallback = ord(char) not in primary_cmap and ord(char) in fallback_cmap
        if needs_fallback != in_fallback:
            flush()
            in_fallback = needs_fallback
        run.append(char)
    flush()
    return "".join(parts)


def _text_runs(text: object, primary: str, fallback: str) -> list[tuple[str, str]]:
    value = "" if text is None else str(text)
    primary_cmap = _font_cmap(primary)
    fallback_cmap = _font_cmap(fallback)
    if not primary_cmap or not fallback_cmap:
        return [(value, primary)]
    runs: list[tuple[str, str]] = []
    current: list[str] = []
    current_font = primary
    for char in value:
        font = (
            fallback
            if ord(char) not in primary_cmap and ord(char) in fallback_cmap
            else primary
        )
        if font != current_font:
            if current:
                runs.append(("".join(current), current_font))
            current = []
            current_font = font
        current.append(char)
    if current:
        runs.append(("".join(current), current_font))
    return runs


def _draw_text(
    canvas,
    x: float,
    y: float,
    text: object,
    font: str,
    size: float,
    fallback: str | None = None,
    *,
    align: str = "left",
) -> None:
    runs = _text_runs(text, font, fallback or font)
    if align == "right":
        x -= sum(pdfmetrics.stringWidth(value, run_font, size) for value, run_font in runs)
    for value, run_font in runs:
        canvas.setFont(run_font, size)
        canvas.drawString(x, y, value)
        x += pdfmetrics.stringWidth(value, run_font, size)


def _value(value: object, available: bool = True) -> str:
    if not available or value is None or value == "":
        return "Non exposé"
    return str(value)


_NUMERIC = re.compile(r"^-?\d+(?:\.\d+)?$")


def _display_decimal(number: Decimal, decimals: int) -> str:
    """Format one Decimal with French separators, without changing it."""
    text = f"{number:,.{decimals}f}"
    return text.replace(",", "\u202f").replace(".", ",")


def _display(value: object, decimals: int) -> str:
    """Format an engine decimal for print without changing the snapshot value."""
    if value is None or value == "":
        return "Non expos\u00e9"
    text = str(value)
    if not _NUMERIC.fullmatch(text):
        return text
    if "." not in text and len(text) < 10:
        return f"{int(text):,}".replace(",", "\u202f")
    try:
        quantum = Decimal(1).scaleb(-decimals)
        rounded = Decimal(text).quantize(quantum, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return text
    return _display_decimal(rounded, decimals)


def _display_kva(value: object, decimals: int) -> str:
    """Present a VA engine value in kVA for the PDF tables."""
    if value is None or value == "":
        return "Non expos\u00e9"
    try:
        number = Decimal(str(value)) / Decimal(1000)
        quantum = Decimal(1).scaleb(-decimals)
        rounded = number.quantize(quantum, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, ZeroDivisionError):
        return str(value)
    return _display_decimal(rounded, decimals)


def _styles() -> dict[str, ParagraphStyle]:
    regular, bold = _register_fonts()
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName=bold,
            fontSize=24,
            leading=28,
            textColor=NAVY,
            spaceAfter=8 * mm,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontName=regular,
            fontSize=12,
            leading=16,
            textColor=RED,
            spaceAfter=4 * mm,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName=bold,
            fontSize=15,
            leading=19,
            textColor=NAVY,
            spaceBefore=4 * mm,
            spaceAfter=3 * mm,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName=bold,
            fontSize=11,
            leading=14,
            textColor=NAVY,
            spaceBefore=3 * mm,
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName=regular,
            fontSize=8.5,
            leading=12,
            textColor=colors.black,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["Normal"],
            fontName=regular,
            fontSize=6.6,
            leading=8.5,
            textColor=colors.black,
        ),
        "smallright": ParagraphStyle(
            "smallright",
            parent=base["Normal"],
            fontName=regular,
            fontSize=6.6,
            leading=8.5,
            alignment=TA_RIGHT,
            textColor=colors.black,
        ),
        "tablehead": ParagraphStyle(
            "tablehead",
            parent=base["Normal"],
            fontName=bold,
            fontSize=6.3,
            leading=7.6,
            textColor=WHITE,
        ),
        "cover_label": ParagraphStyle(
            "cover_label",
            parent=base["Normal"],
            fontName=bold,
            fontSize=8,
            leading=10,
            textColor=MUTED,
        ),
        "cover_value": ParagraphStyle(
            "cover_value",
            parent=base["Normal"],
            fontName=regular,
            fontSize=10,
            leading=13,
            textColor=NAVY,
        ),
    }


def _header_footer(canvas, doc) -> None:
    regular, _ = _register_fonts()
    canvas.saveState()
    width, height = doc.pagesize
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 14 * mm, width, 14 * mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 7.5)
    canvas.drawString(15 * mm, height - 8.5 * mm, "SEGYRCALC · Bilan de puissance électrique")
    project = getattr(doc, "_report_project", "")
    _draw_text(
        canvas,
        width - 15 * mm,
        height - 8.5 * mm,
        project[:100],
        regular,
        6.5,
        _FALLBACK_REGULAR,
        align="right",
    )
    canvas.setStrokeColor(RED)
    canvas.setLineWidth(0.8)
    canvas.line(15 * mm, 12 * mm, width - 15 * mm, 12 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 6.3)
    canvas.drawString(15 * mm, 7 * mm, "Document généré localement · résultats moteur SEGYRCALC")
    canvas.drawRightString(width - 15 * mm, 7 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _cover_page(canvas, doc) -> None:
    canvas.saveState()
    width, height = doc.pagesize
    canvas.setFillColor(LIGHT)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 68 * mm, width, 68 * mm, fill=1, stroke=0)
    canvas.setFillColor(RED)
    canvas.rect(0, height - 70 * mm, width, 2 * mm, fill=1, stroke=0)
    canvas.restoreState()


def _p(text: object, style: ParagraphStyle, *, available: bool = True) -> Paragraph:
    primary = str(style.fontName)
    fallback = _FALLBACK_BOLD if "Bold" in primary else _FALLBACK_REGULAR
    return Paragraph(_markup(_value(text, available), primary, fallback), style)


def _table(
    data: Sequence[Sequence[Any]],
    widths: list[float],
    styles: dict[str, ParagraphStyle],
    *,
    numeric_from: int | None = None,
    decimals: int = 2,
) -> LongTable:
    prepared: list[list[object]] = []
    for row_index, row in enumerate(data):
        prepared_row: list[object] = []
        for column_index, cell in enumerate(row):
            if row_index == 0:
                prepared_row.append(_p(cell, styles["tablehead"]))
            elif isinstance(cell, Paragraph):
                prepared_row.append(cell)
            else:
                style = (
                    styles["smallright"]
                    if numeric_from is not None and column_index >= numeric_from
                    else styles["small"]
                )
                prepared_row.append(_p(_display(cell, decimals), style))
        prepared.append(prepared_row)
    table = LongTable(prepared, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("GRID", (0, 0), (-1, -1), 0.3, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
                ("TOPPADDING", (0, 0), (-1, -1), 2.2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT]),
            ]
        )
    )
    return table


def _summary_rows(snapshot: ReportSnapshot) -> list[list[object]]:
    totals = snapshot.payload.get("totals", {})
    return [
        ["Indicateur", "Valeur", "Unité"],
        ["Puissance installée", totals.get("p_installed_w"), "W"],
        ["Puissance après Ku", totals.get("p_after_ku_w"), "W"],
        ["Puissance retenue", totals.get("p_after_ks_w"), "W"],
        ["Puissance réactive après Ku", totals.get("q_after_ku_var"), "var"],
        ["Puissance réactive retenue", totals.get("q_after_ks_var"), "var"],
        ["Puissance apparente après Ku", _display_kva(totals.get("s_after_ku_va"), 2), "kVA"],
        ["Puissance apparente retenue", _display_kva(totals.get("s_after_ks_va"), 2), "kVA"],
        ["Courant neutre", totals.get("neutral_current_a"), "A"],
        ["Déséquilibre", totals.get("unbalance_percent"), "%"],
        ["Cos φ global", _value(None, False), "—"],
    ]


def _receivers_table(
    snapshot: ReportSnapshot,
    styles: dict[str, ParagraphStyle],
    portrait: bool,
    decimals: int,
) -> LongTable:
    rows = snapshot.payload.get("loads", [])
    if portrait:
        data: list[list[object]] = [
            [
                "R\u00e9f.",
                "D\u00e9signation",
                "D\u00e9part",
                "Type",
                "Qt\u00e9",
                "Ku",
                "Ks",
                "P retenue (W)",
                "Q retenue (var)",
                "S retenue (kVA)",
                "I retenue (A)",
                "Phase",
                "\u00c9tat",
            ]
        ]
        for item in rows:
            s_value = (
                _display_kva(item.get("s_after_ks_va"), decimals)
                if item.get("apparent_power_available")
                else "Non expos\u00e9"
            )
            i_value = (
                _display(item.get("current_a"), decimals)
                if item.get("current_available")
                else "Non expos\u00e9"
            )
            data.append(
                [
                    item.get("id"),
                    item.get("designation"),
                    item.get("feeder_id"),
                    item.get("network"),
                    item.get("quantity"),
                    item.get("ku"),
                    item.get("ks") or "\u2014",
                    item.get("p_after_ks_w"),
                    item.get("q_after_ks_var"),
                    s_value,
                    i_value,
                    item.get("phase") or "\u2014",
                    item.get("status"),
                ]
            )
        widths = [
            11 * mm,
            26 * mm,
            15 * mm,
            10 * mm,
            6 * mm,
            7 * mm,
            7 * mm,
            16 * mm,
            15 * mm,
            18 * mm,
            18 * mm,
            10 * mm,
            23 * mm,
        ]
        numeric_from = 4
    else:
        data = [
            [
                "R\u00e9f.",
                "D\u00e9signation",
                "Tableau",
                "D\u00e9part",
                "Type",
                "Qt\u00e9",
                "U",
                "Cos \u03c6",
                "Ku",
                "Ks",
                "P inst. (W)",
                "P Ku (W)",
                "P retenue (W)",
                "Q retenue (var)",
                "S retenue (kVA)",
                "I retenue (A)",
                "Phase",
                "\u00c9tat",
            ]
        ]
        for item in rows:
            s_value = (
                _display_kva(item.get("s_after_ks_va"), decimals)
                if item.get("apparent_power_available")
                else "Non expos\u00e9"
            )
            i_value = (
                _display(item.get("current_a"), decimals)
                if item.get("current_available")
                else "Non expos\u00e9"
            )
            data.append(
                [
                    item.get("id"),
                    item.get("designation"),
                    item.get("parent_board_id"),
                    item.get("feeder_id"),
                    item.get("network"),
                    item.get("quantity"),
                    item.get("voltage_v"),
                    item.get("power_factor"),
                    item.get("ku"),
                    item.get("ks"),
                    item.get("installed_power_w"),
                    item.get("p_after_ku_w"),
                    item.get("p_after_ks_w"),
                    item.get("q_after_ks_var"),
                    s_value,
                    i_value,
                    item.get("phase") or "\u2014",
                    item.get("status"),
                ]
            )
        widths = [
            12 * mm,
            48 * mm,
            15 * mm,
            15 * mm,
            10 * mm,
            7 * mm,
            8 * mm,
            8 * mm,
            7 * mm,
            7 * mm,
            16 * mm,
            16 * mm,
            17 * mm,
            17 * mm,
            18 * mm,
            18 * mm,
            8 * mm,
            22 * mm,
        ]
        numeric_from = 5
    return _table(data, widths, styles, numeric_from=numeric_from, decimals=decimals)


def generate_pdf(snapshot: ReportSnapshot) -> bytes:
    styles = _styles()
    portrait = snapshot.config.orientation == "portrait"
    pagesize = A4 if portrait else landscape(A4)
    margin = 14 * mm
    buffer = BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=22 * mm,
        bottomMargin=18 * mm,
        title=snapshot.config.title,
        author="SEGYR Technologies",
        subject=f"{snapshot.project_reference} · révision {snapshot.revision}",
        creator="SEGYRCALC Web Desktop",
    )
    doc._report_project = snapshot.project_reference  # type: ignore[attr-defined]
    frame = Frame(margin, 16 * mm, pagesize[0] - 2 * margin, pagesize[1] - 38 * mm, id="main")
    cover_frame = Frame(
        margin,
        16 * mm,
        pagesize[0] - 2 * margin,
        pagesize[1] - 92 * mm,
        id="cover-main",
    )
    doc.addPageTemplates(
        [
            PageTemplate(id="cover", frames=[cover_frame], onPage=_cover_page, pagesize=pagesize),
            PageTemplate(id="body", frames=[frame], onPage=_header_footer, pagesize=pagesize),
        ]
    )
    story: list[object] = [NextPageTemplate("body")]
    config = snapshot.config
    payload = snapshot.payload
    project = payload.get("project", {})
    engine = payload.get("engine", {})

    if "cover" in config.sections:
        if LOGO.is_file():
            try:
                story.append(Image(str(LOGO), width=42 * mm, height=18 * mm, kind="proportional"))
                story.append(Spacer(1, 8 * mm))
            except Exception:
                pass
        story.append(_p(config.title, styles["title"]))
        story.append(_p("SEGYRCALC · Bilan de puissance électrique", styles["subtitle"]))
        story.append(Spacer(1, 12 * mm))
        cover_data = [
            [_p("Projet", styles["cover_label"]), _p(project.get("name"), styles["cover_value"])],
            [
                _p("Référence", styles["cover_label"]),
                _p(project.get("reference"), styles["cover_value"]),
            ],
            [
                _p("Client", styles["cover_label"]),
                _p(project.get("client") or "—", styles["cover_value"]),
            ],
            [
                _p("Site", styles["cover_label"]),
                _p(payload.get("web", {}).get("site") or "—", styles["cover_value"]),
            ],
            [_p("Révision", styles["cover_label"]), _p(snapshot.revision, styles["cover_value"])],
            [
                _p("Date d'édition", styles["cover_label"]),
                _p(snapshot.created_at.date().isoformat(), styles["cover_value"]),
            ],
            [
                _p("Logiciel", styles["cover_label"]),
                _p("SEGYRCALC Web Desktop · module Rapports", styles["cover_value"]),
            ],
        ]
        cover = Table(cover_data, colWidths=[38 * mm, 122 * mm])
        cover.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.3, BORDER),
                ]
            )
        )
        story.append(cover)
        story.append(PageBreak())

    if "general" in config.sections:
        story.append(_p("1. Informations générales", styles["h1"]))
        general = [
            ["Information", "Valeur"],
            ["Nom du projet", project.get("name")],
            ["Référence affaire", project.get("reference")],
            ["Client", project.get("client") or "—"],
            ["Site", payload.get("web", {}).get("site") or "—"],
            ["Adresse", payload.get("web", {}).get("address") or "—"],
            ["Auteur", payload.get("web", {}).get("created_by") or "—"],
            ["Description", project.get("description") or "—"],
            ["Observations", payload.get("web", {}).get("observations") or "—"],
        ]
        story.append(_table(general, [48 * mm, 112 * mm], styles))

    if "summary" in config.sections:
        story.append(_p("2. Synthèse générale TGBT", styles["h1"]))
        story.append(
            _table(
                _summary_rows(snapshot),
                [70 * mm, 65 * mm, 25 * mm],
                styles,
                numeric_from=1,
                decimals=config.decimals,
            )
        )
        story.append(Spacer(1, 3 * mm))
        story.append(
            _p(
                "Les valeurs sont celles du moteur au moment du snapshot. Le cos φ global n'est pas exposé par le moteur.",
                styles["body"],
            )
        )

    if "architecture" in config.sections:
        story.append(_p("3. Architecture électrique", styles["h1"]))
        arch = [
            ["Référence", "Désignation", "Type", "Réseau", "Tension (V)", "Départs", "Réc.", "État"]
        ]
        for item in payload.get("boards", []):
            arch.append(
                [
                    item.get("id"),
                    item.get("designation"),
                    item.get("type"),
                    item.get("network"),
                    item.get("voltage_v"),
                    item.get("feeder_count"),
                    item.get("load_count"),
                    item.get("status"),
                ]
            )
        story.append(
            _table(
                arch,
                [16 * mm, 48 * mm, 20 * mm, 14 * mm, 18 * mm, 14 * mm, 22 * mm, 30 * mm],
                styles,
                numeric_from=5,
                decimals=config.decimals,
            )
        )

    story.append(CondPageBreak(45 * mm))
    if "boards" in config.sections:
        story.append(_p("4. Synthèses des tableaux divisionnaires", styles["h1"]))
        data = [
            [
                "Réf.",
                "Désignation",
                "P inst. (W)",
                "P Ku (W)",
                "P retenue (W)",
                "Q retenue (var)",
                "S retenue (kVA)",
                "Déséquilibre (%)",
                "État",
            ]
        ]
        for item in payload.get("boards", []):
            data.append(
                [
                    item.get("id"),
                    item.get("designation"),
                    item.get("p_installed_w"),
                    item.get("p_after_ku_w"),
                    item.get("p_after_ks_w"),
                    item.get("q_after_ks_var"),
                    _display_kva(item.get("s_after_ks_va"), config.decimals),
                    item.get("unbalance_percent"),
                    item.get("status"),
                ]
            )
        story.append(
            _table(
                data,
                [11 * mm, 38 * mm, 16 * mm, 16 * mm, 16 * mm, 16 * mm, 17 * mm, 17 * mm, 35 * mm],
                styles,
                numeric_from=2,
                decimals=config.decimals,
            )
        )

    story.append(CondPageBreak(45 * mm))
    if "feeders" in config.sections:
        story.append(_p("5. Bilan des départs", styles["h1"]))
        data = [
            [
                "Réf.",
                "Désignation",
                "Tableau",
                "Réc.",
                "Ks",
                "P inst. (W)",
                "P Ku (W)",
                "P retenue (W)",
                "Q retenue (var)",
                "S retenue (kVA)",
                "État",
            ]
        ]
        for item in payload.get("feeders", []):
            data.append(
                [
                    item.get("id"),
                    item.get("designation"),
                    item.get("parent_board_id"),
                    item.get("member_count"),
                    item.get("ks") or "—",
                    item.get("p_installed_w"),
                    item.get("p_after_ku_w"),
                    item.get("p_after_ks_w"),
                    item.get("q_after_ks_var"),
                    _display_kva(item.get("s_after_ks_va"), config.decimals),
                    item.get("status"),
                ]
            )
        story.append(
            _table(
                data,
                [
                    11 * mm,
                    34 * mm,
                    15 * mm,
                    8 * mm,
                    8 * mm,
                    15 * mm,
                    15 * mm,
                    16 * mm,
                    15 * mm,
                    17 * mm,
                    28 * mm,
                ],
                styles,
                numeric_from=3,
                decimals=config.decimals,
            )
        )

    if "receivers" in config.sections:
        story.append(PageBreak())
        story.append(_p("6. Bilan détaillé des récepteurs", styles["h1"]))
        story.append(
            _p(
                "S/I individuels issus des contributions moteur après Ku et Ks ; une valeur absente est indiquée « Non exposé ».",
                styles["body"],
            )
        )
        story.append(_receivers_table(snapshot, styles, portrait, config.decimals))

    story.append(CondPageBreak(45 * mm))
    if "coefficients" in config.sections:
        story.append(CondPageBreak(45 * mm))
        story.append(_p("7. Coefficients Ku et Ks", styles["h1"]))
        data = [["Élément", "Type", "Ku", "Ks"]]
        for item in payload.get("loads", []):
            data.append(
                [
                    f"{item.get('id')} · {item.get('designation')}",
                    "Récepteur",
                    item.get("ku"),
                    item.get("ks"),
                ]
            )
        for item in payload.get("feeders", []):
            data.append(
                [f"{item.get('id')} · {item.get('designation')}", "Départ", "—", item.get("ks") or "—"]
            )
        story.append(
            _table(
                data,
                [90 * mm, 40 * mm, 20 * mm, 20 * mm],
                styles,
                numeric_from=2,
                decimals=config.decimals,
            )
        )

    story.append(CondPageBreak(45 * mm))
    if "phases" in config.sections:
        story.append(_p("8. Répartition des phases et déséquilibre", styles["h1"]))
        phases = payload.get("totals", {})
        phase_data: list[list[object]] = [["Phase", "P (W)", "Q (var)", "S (kVA)", "I (A)"]]
        for phase in ("l1", "l2", "l3"):
            phase_data.append(
                [
                    phase.upper(),
                    (phases.get("p_phases") or {}).get(phase),
                    (phases.get("q_phases") or {}).get(phase),
                    _display_kva((phases.get("s_phases") or {}).get(phase), config.decimals),
                    (phases.get("current_phases") or {}).get(phase),
                ]
            )
        story.append(
            _table(
                phase_data,
                [25 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm],
                styles,
                numeric_from=1,
                decimals=config.decimals,
            )
        )
        story.append(
            _p(
                f"Neutre : {_display(phases.get('neutral_current_a'), config.decimals)} A · Déséquilibre : {_display(phases.get('unbalance_percent'), config.decimals)} %",
                styles["body"],
            )
        )
        story.append(
            _p("Valeurs moteur, sans répartition théorique recalculée.", styles["body"])
        )

    story.append(CondPageBreak(45 * mm))
    if "assumptions" in config.sections and config.include_assumptions:
        story.append(_p("9. Hypothèses et limites", styles["h1"]))
        for item in payload.get("assumptions", []):
            story.append(_p(f"• {item}", styles["body"]))
        story.append(
            _p(
                "S/I individuels récepteur : issus des contributions moteur après Ku et Ks. Cos φ global : non exposé. Les résultats ne constituent pas une note de calcul normative complète.",
                styles["body"],
            )
        )

    if "traceability" in config.sections and config.include_traceability:
        story.append(_p("10. Traçabilité des résultats", styles["h1"]))
        trace: list[list[object]] = [
            ["Élément", "Valeur"],
            ["Identifiant projet", snapshot.project_id],
            ["Référence", snapshot.project_reference],
            ["Révision projet", snapshot.revision],
            ["Révision calculée", snapshot.calculation_revision],
            ["Moteur", engine.get("facade")],
            ["Version moteur", engine.get("version")],
            ["Empreinte source moteur", engine.get("engine_source_sha256")],
            ["Empreinte snapshot", snapshot.source_sha256],
            ["Date de calcul", payload.get("calculated_at")],
            ["Statut", payload.get("status")],
        ]
        story.append(_table(trace, [62 * mm, 98 * mm], styles))

    doc.build(story)
    return buffer.getvalue()
