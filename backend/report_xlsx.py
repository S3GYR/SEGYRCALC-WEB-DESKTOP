"""OpenXML XLSX generation for WEB-06 reports.

The workbook contains values copied from the frozen report snapshot. It never
contains electrical formulas, macros, external links or data connections.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .reporting import ReportSnapshot, build_preview

NAVY = "13263E"
RED = "B52432"
LIGHT = "F2F5F8"
BORDER = "D5DEE8"
WHITE = "FFFFFF"
FORMULA_PREFIXES = ("=", "+", "-", "@")


def _safe(value: Any) -> str:
    if value is None or value == "":
        return "Non exposé"
    text = str(value)
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def _header(ws: Worksheet, headers: list[str], widths: list[float] | None = None) -> None:
    ws.append(headers)
    for index, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=index)
        cell.value = header
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.font = Font(color=WHITE, bold=True, size=9)
        cell.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)
        cell.border = Border(bottom=Side(style="thin", color=RED))
    ws.row_dimensions[1].height = 34
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    ws.sheet_view.showGridLines = False
    for index, width in enumerate(widths or [], start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.print_title_rows = "1:1"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def _rows(ws: Worksheet, rows: list[list[Any]], numeric_columns: set[int] | None = None) -> None:
    numeric_columns = numeric_columns or set()
    for row in rows:
        ws.append([_safe(value) for value in row])
        row_index = ws.max_row
        for column_index in range(1, len(row) + 1):
            cell = ws.cell(row=row_index, column=column_index)
            cell.font = Font(size=8.5)
            cell.alignment = Alignment(
                vertical="top",
                horizontal="right" if column_index in numeric_columns else "left",
                wrap_text=column_index in {2},
            )
            if row_index % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=LIGHT)
            cell.border = Border(bottom=Side(style="hair", color=BORDER))


def _finish(ws: Worksheet, red_tab: bool = False) -> None:
    if red_tab:
        ws.sheet_properties.tabColor = RED
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.oddFooter.center.text = "SEGYRCALC · rapport généré localement · Page &P/&N"
    ws.oddFooter.center.size = 8
    ws.oddFooter.center.color = "5D6B7A"


def _summary_sheet(ws: Worksheet, preview: dict[str, Any]) -> None:
    snapshot = preview["snapshot"]
    totals = preview["summary"]["totals"]
    project = preview["summary"]["project"]
    _header(ws, ["Indicateur", "Valeur", "Unité"], [58, 34, 16])
    rows = [
        ["Projet", project.get("name"), ""],
        ["Référence", project.get("reference"), ""],
        ["Client", project.get("client"), ""],
        ["Révision projet", snapshot.get("revision"), ""],
        ["Révision calculée", snapshot.get("calculation_revision"), ""],
        ["Date de génération", snapshot.get("created_at"), ""],
        ["Puissance installée", totals.get("p_installed_w"), "W"],
        ["Puissance après Ku", totals.get("p_after_ku_w"), "W"],
        ["Puissance retenue", totals.get("p_after_ks_w"), "W"],
        ["Puissance réactive après Ku", totals.get("q_after_ku_var"), "var"],
        ["Puissance réactive retenue", totals.get("q_after_ks_var"), "var"],
        ["Puissance apparente après Ku", totals.get("s_after_ku_va"), "VA"],
        ["Puissance apparente retenue", totals.get("s_after_ks_va"), "VA"],
        ["Courant neutre", totals.get("neutral_current_a"), "A"],
        ["Déséquilibre", totals.get("unbalance_percent"), "%"],
        ["Cos φ global", "Non exposé", "—"],
        ["S/I récepteur individuels", "Contributions moteur après Ku et Ks", "—"],
        ["Statut de cohérence", preview["coherence"].get("status"), ""],
        ["Empreinte snapshot", snapshot.get("source_sha256"), ""],
    ]
    _rows(ws, rows, {2})
    ws.column_dimensions["A"].width = 58
    ws.column_dimensions["B"].width = 46
    ws.column_dimensions["C"].width = 16
    _finish(ws, red_tab=True)


def _project_sheet(ws: Worksheet, preview: dict[str, Any]) -> None:
    snapshot = preview["snapshot"]
    project = preview["summary"]["project"]
    totals = preview["summary"]["totals"]
    _header(ws, ["Rubrique", "Valeur", "Unité"], [54, 42, 16])
    rows = [
        ["Nom", project.get("name"), ""],
        ["Référence", project.get("reference"), ""],
        ["Client", project.get("client"), ""],
        ["Description", project.get("description"), ""],
        ["Nombre de tableaux", project.get("board_count"), ""],
        ["Nombre de départs", project.get("feeder_count"), ""],
        ["Nombre de récepteurs", project.get("load_count"), ""],
        ["P installée", totals.get("p_installed_w"), "W"],
        ["P après Ku", totals.get("p_after_ku_w"), "W"],
        ["P retenue", totals.get("p_after_ks_w"), "W"],
        ["Q retenue", totals.get("q_after_ks_var"), "var"],
        ["S retenue", totals.get("s_after_ks_va"), "VA"],
        ["I neutre", totals.get("neutral_current_a"), "A"],
        ["Déséquilibre", totals.get("unbalance_percent"), "%"],
        ["Révision", snapshot.get("revision"), ""],
        ["Calculée", snapshot.get("calculation_revision"), ""],
        ["Moteur", preview["traceability"].get("engine", {}).get("facade"), ""],
        ["Version moteur", preview["traceability"].get("engine", {}).get("version"), ""],
    ]
    _rows(ws, rows, {2})
    _finish(ws)


def _board_sheet(ws: Worksheet, preview: dict[str, Any]) -> None:
    headers = [
        "Référence",
        "Désignation",
        "Type",
        "Réseau",
        "Tension (V)",
        "Départs",
        "Récepteurs",
        "P installée (W)",
        "P Ku (W)",
        "P retenue (W)",
        "Q retenue (var)",
        "S retenue (VA)",
        "I neutre (A)",
        "Déséquilibre (%)",
        "État",
    ]
    _header(ws, headers, [16, 34, 14, 11, 13, 10, 12, 18, 18, 18, 18, 18, 14, 16, 14])
    rows = [
        [
            item.get("reference"),
            item.get("designation"),
            item.get("type"),
            item.get("network"),
            item.get("voltage_v"),
            item.get("feeders"),
            item.get("receivers"),
            item.get("p_installed_w"),
            item.get("p_after_ku_w"),
            item.get("p_after_ks_w"),
            item.get("q_after_ks_var"),
            item.get("s_after_ks_va"),
            item.get("neutral_current_a"),
            item.get("unbalance_percent"),
            item.get("status"),
        ]
        for item in preview["boards"]
    ]
    _rows(ws, rows, {6, 7, 8, 9, 10, 11, 12, 13})
    _finish(ws)


def _feeder_sheet(ws: Worksheet, preview: dict[str, Any]) -> None:
    headers = [
        "Référence",
        "Désignation",
        "Tableau",
        "Réseau",
        "Tension (V)",
        "Récepteurs",
        "Ks",
        "P installée (W)",
        "P Ku (W)",
        "P retenue (W)",
        "Q retenue (var)",
        "S retenue (VA)",
        "I neutre (A)",
        "Déséquilibre (%)",
        "État",
    ]
    _header(ws, headers, [16, 34, 16, 11, 13, 12, 10, 18, 18, 18, 18, 18, 14, 16, 14])
    rows = [
        [
            item.get("reference"),
            item.get("designation"),
            item.get("board"),
            item.get("network"),
            item.get("voltage_v"),
            item.get("receivers"),
            item.get("ks"),
            item.get("p_installed_w"),
            item.get("p_after_ku_w"),
            item.get("p_after_ks_w"),
            item.get("q_after_ks_var"),
            item.get("s_after_ks_va"),
            item.get("neutral_current_a"),
            item.get("unbalance_percent"),
            item.get("status"),
        ]
        for item in preview["feeders"]
    ]
    _rows(ws, rows, {6, 7, 8, 9, 10, 11, 12, 13})
    _finish(ws)


def _receiver_sheet(ws: Worksheet, preview: dict[str, Any]) -> None:
    headers = [
        "Référence",
        "Désignation",
        "Tableau",
        "Départ",
        "Réseau",
        "Tension (V)",
        "Qté",
        "P installée (W)",
        "Cos φ",
        "Ku",
        "Ks",
        "P Ku (W)",
        "P retenue (W)",
        "Q Ku (var)",
        "Q retenue (var)",
        "S (VA)",
        "I (A)",
        "Phase",
        "État",
    ]
    _header(ws, headers, [16, 36, 16, 16, 11, 13, 9, 17, 10, 9, 9, 17, 17, 16, 16, 15, 15, 10, 14])
    rows = [
        [
            item.get("reference"),
            item.get("designation"),
            item.get("board"),
            item.get("feeder"),
            item.get("network"),
            item.get("voltage_v"),
            item.get("quantity"),
            item.get("installed_power_w"),
            item.get("power_factor"),
            item.get("ku"),
            item.get("ks"),
            item.get("p_after_ku_w"),
            item.get("p_after_ks_w"),
            item.get("q_after_ku_var"),
            item.get("q_after_ks_var"),
            "Non exposé" if not item.get("s_available") else item.get("s_after_ks_va"),
            "Non exposé" if not item.get("i_available") else item.get("current_a"),
            item.get("phase"),
            item.get("status"),
        ]
        for item in preview["receivers"]
    ]
    _rows(ws, rows, {7, 8, 9, 10, 11, 12, 13, 14, 15})
    _finish(ws)


def _phase_sheet(ws: Worksheet, preview: dict[str, Any]) -> None:
    phases = preview["phases"]
    _header(ws, ["Phase", "P (W)", "Q (var)", "S (VA)", "I (A)"], [18, 28, 28, 28, 28])
    rows = []
    for key in ("l1", "l2", "l3"):
        rows.append(
            [
                key.upper(),
                (phases.get("p") or {}).get(key),
                (phases.get("q") or {}).get(key),
                (phases.get("s") or {}).get(key),
                (phases.get("i") or {}).get(key),
            ]
        )
    rows.append(["Neutre", "", "", "", phases.get("neutral")])
    rows.append(["Déséquilibre (%)", "", "", "", phases.get("unbalance")])
    _rows(ws, rows, {2, 3, 4, 5})
    _finish(ws)


def _assumptions_sheet(ws: Worksheet, preview: dict[str, Any]) -> None:
    _header(ws, ["Hypothèse / limite"], [100])
    _rows(ws, [[item] for item in preview["assumptions"]], set())
    for extra in (
        "S/I individuels récepteur issus des contributions moteur après Ku et Ks.",
        "Cos φ global non exposé par le moteur.",
        "Les valeurs exportées ne sont pas des formules de recalcul.",
        "Les cellules texte commençant par =, +, - ou @ sont neutralisées par apostrophe.",
    ):
        ws.append([extra])
    _finish(ws)


def _trace_sheet(ws: Worksheet, preview: dict[str, Any]) -> None:
    snapshot = preview["snapshot"]
    engine = preview["traceability"].get("engine", {})
    _header(ws, ["Élément", "Valeur"], [42, 90])
    rows = [
        ["Identifiant projet", snapshot.get("project_id")],
        ["Référence", snapshot.get("project_reference")],
        ["Révision projet", snapshot.get("revision")],
        ["Révision calculée", snapshot.get("calculation_revision")],
        ["Moteur", engine.get("facade")],
        ["Version moteur", engine.get("version")],
        ["Source moteur", engine.get("source")],
        ["Empreinte source moteur", engine.get("engine_source_sha256")],
        ["Empreinte snapshot", snapshot.get("source_sha256")],
        ["Date de génération", snapshot.get("created_at")],
        ["Date de calcul", engine.get("calculated_at") or preview["summary"].get("calculated_at")],
        ["Statut de cohérence", preview["coherence"].get("status")],
        ["Version rapport", "WEB-06 / 1"],
    ]
    _rows(ws, rows, {2})
    _finish(ws)


def generate_xlsx(snapshot: ReportSnapshot) -> bytes:
    preview = build_preview(snapshot)
    wb = Workbook()
    wb.properties.creator = "SEGYR Technologies"
    wb.properties.title = snapshot.config.title
    wb.properties.subject = f"{snapshot.project_reference} · révision {snapshot.revision}"
    wb.properties.description = "Rapport technique SEGYRCALC généré localement."
    wb.calculation.fullCalcOnLoad = False

    summary = wb.active
    summary.title = "Synthèse"
    _summary_sheet(summary, preview)

    project = wb.create_sheet("TGBT")
    _project_sheet(project, preview)
    boards = wb.create_sheet("Tableaux")
    _board_sheet(boards, preview)
    feeders = wb.create_sheet("Départs")
    _feeder_sheet(feeders, preview)
    receivers = wb.create_sheet("Récepteurs")
    _receiver_sheet(receivers, preview)
    phases = wb.create_sheet("Phases")
    _phase_sheet(phases, preview)
    assumptions = wb.create_sheet("Hypothèses")
    _assumptions_sheet(assumptions, preview)
    trace = wb.create_sheet("Traçabilité")
    _trace_sheet(trace, preview)

    for sheet in wb.worksheets:
        sheet.sheet_view.zoomScale = 90
        sheet.page_margins.left = 0.3
        sheet.page_margins.right = 0.3
        sheet.page_margins.top = 0.6
        sheet.page_margins.bottom = 0.6
        sheet.page_margins.header = 0.2
        sheet.page_margins.footer = 0.2

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
