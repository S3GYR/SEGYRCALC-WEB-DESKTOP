from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.project_commands import CommandProjectStore

TOKEN = "encoding-s2-report-options"
AUTH = {"X-SEGYR-Token": TOKEN}
EXPECTED = [
    "Page de garde",
    "Informations générales",
    "Synthèse générale TGBT",
    "Architecture électrique",
    "Synthèses des tableaux",
    "Bilan des départs",
    "Bilan des récepteurs",
    "Coefficients Ku et Ks",
    "Répartition des phases",
    "Hypothèses et limites",
    "Traçabilité",
]
MOJIBAKE = (
    chr(0xC3) + chr(0xA9),
    chr(0xC3) + chr(0xA8),
    chr(0xC3) + chr(0xAA),
    chr(0xC3) + chr(0xA7),
    chr(0xC3) + chr(0x0192),
    chr(0xC2) + chr(0xA9),
    chr(0xFFFD),
)


def test_report_options_have_clean_french_labels(tmp_path: Path) -> None:
    store = CommandProjectStore(root=tmp_path / "projects")
    with TestClient(create_app(TOKEN, allow_test_host=True, project_store=store)) as api:
        response = api.get("/api/reports/options", headers=AUTH)
        assert response.status_code == 200, response.text
        sections = response.json()["sections"]
        labels = [section["label"] for section in sections]
        assert labels == EXPECTED
        for label in labels:
            for pattern in MOJIBAKE:
                assert pattern not in label, (label, pattern)
