"""CSV generation for WEB-06 reports.

Dialect: UTF-8 with BOM, semicolon separator, CRLF line endings, minimal
quoting. This profile is directly usable in French Excel while remaining a
standard RFC 4180-style CSV. Text beginning with a spreadsheet formula marker
is prefixed with an apostrophe; the project data itself is never modified.
"""

from __future__ import annotations

import csv
import io
from functools import partial
from typing import Any

from .presentation import engine_display_name
from .reporting import ReportSnapshot, build_preview

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _safe(value: Any) -> str:
    text = "" if value is None else str(value)
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def _result(value: Any) -> str:
    if value is None or value == "":
        return "Non exposé"
    return _safe(value)


def _write(headers: list[str], rows: list[list[Any]], delimiter: str = ";") -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(
        buffer,
        delimiter=delimiter,
        quotechar='"',
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\r\n",
    )
    writer.writerow([_safe(item) for item in headers])
    for row in rows:
        writer.writerow([_safe(item) for item in row])
    return buffer.getvalue().encode("utf-8-sig")


def generate_csv_files(snapshot: ReportSnapshot) -> dict[str, bytes]:
    preview = build_preview(snapshot)
    write = partial(_write, delimiter=snapshot.config.csv_delimiter)
    totals = preview["summary"]["totals"]
    project = preview["summary"]["project"]
    engine = preview["traceability"].get("engine", {})

    synthesis = write(
        ["Indicateur", "Valeur", "Unité"],
        [
            ["Projet", project.get("name"), ""],
            ["Référence", project.get("reference"), ""],
            ["Client", project.get("client"), ""],
            ["Révision projet", preview["snapshot"].get("revision"), ""],
            ["Révision calculée", preview["snapshot"].get("calculation_revision"), ""],
            ["Date de génération", preview["snapshot"].get("created_at"), ""],
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
            ["Statut cohérence", preview["coherence"].get("status"), ""],
            ["Empreinte snapshot", preview["snapshot"].get("source_sha256"), ""],
        ],
    )

    boards = write(
        [
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
        ],
        [
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
        ],
    )

    feeders = write(
        [
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
        ],
        [
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
        ],
    )

    receivers = write(
        [
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
        ],
        [
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
        ],
    )

    phases = preview["phases"]
    phase_rows = []
    for key in ("l1", "l2", "l3"):
        phase_rows.append(
            [
                key.upper(),
                (phases.get("p") or {}).get(key),
                (phases.get("q") or {}).get(key),
                (phases.get("s") or {}).get(key),
                (phases.get("i") or {}).get(key),
            ]
        )
    phase_rows.append(["Neutre", "", "", "", phases.get("neutral")])
    phase_rows.append(["Déséquilibre (%)", "", "", "", phases.get("unbalance")])
    phase_file = write(["Phase", "P (W)", "Q (var)", "S (VA)", "I (A)"], phase_rows)

    trace = write(
        ["Élément", "Valeur"],
        [
            ["Identifiant projet", preview["snapshot"].get("project_id")],
            ["Référence", preview["snapshot"].get("project_reference")],
            ["Révision projet", preview["snapshot"].get("revision")],
            ["Révision calculée", preview["snapshot"].get("calculation_revision")],
            ["Moteur", engine_display_name(engine.get("facade"))],
            ["Version moteur", engine.get("version")],
            ["Source moteur", engine.get("source")],
            ["Empreinte source moteur", engine.get("engine_source_sha256")],
            ["Empreinte snapshot", preview["snapshot"].get("source_sha256")],
            ["Date de génération", preview["snapshot"].get("created_at")],
            ["Statut cohérence", preview["coherence"].get("status")],
            ["Version rapport", "WEB-06 / 1"],
        ],
    )

    return {
        "synthese.csv": synthesis,
        "tableaux.csv": boards,
        "departs.csv": feeders,
        "recepteurs.csv": receivers,
        "phases.csv": phase_file,
        "tracabilite.csv": trace,
    }
