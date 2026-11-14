from __future__ import annotations

import tempfile
from pathlib import Path

from backend.project_commands import CommandProjectStore
from backend.reporting import ReportConfig, ReportService


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="segyr-report-"))
    store = CommandProjectStore(root=root / "projects")
    store.new(
        name="Projet rapport test",
        reference="WEB06-SMOKE",
        client="Client test",
        site="Site test",
        address="1 rue de test",
        author="Qualification",
        description="Projet de validation",
        observations="",
        revision="A",
        standard="NF C 15-100",
        network="TRI",
        voltage_v="400",
        has_neutral=True,
        voltage_ln_v="230",
    )
    payload = store._payload()
    board = payload["boards"][0]
    feeder = store.add_feeder(
        {
            "expected_revision": payload["state"]["revision"],
            "parent_board_id": board["id"],
            "designation": "Départ éclairage",
            "description": "",
            "ks": "0.9",
            "phase": None,
            "has_neutral": True,
            "voltage_ln_v": "230",
        }
    )
    feeder_id = feeder["feeders"][0]["id"]
    for index in range(5):
        store.add_load(
            {
                "expected_revision": store._payload()["state"]["revision"],
                "feeder_id": feeder_id,
                "designation": f"Récepteur éclairage {index + 1}",
                "network": "MONO",
                "voltage_v": "230",
                "nominal_power": "1200",
                "power_unit": "W",
                "quantity": 2,
                "power_factor": "0.92",
                "ku": "0.8",
                "phase": ["L1", "L2", "L3", None, "L1"][index],
            }
        )
    service = ReportService(root=root / "exports")
    config = ReportConfig(title="Bilan de puissance — qualification", decimals=2)
    preview = service.preview(store, config)
    snapshot_id = preview["snapshot"]["snapshot_id"]
    print("snapshot", snapshot_id, preview["snapshot"]["source_sha256"])
    print("receivers", len(preview["receivers"]), "boards", len(preview["boards"]))
    for format_name, path in (
        ("pdf", root / "exports" / "rapport.pdf"),
        ("xlsx", root / "exports" / "rapport.xlsx"),
        ("csv", root / "exports" / "csv"),
    ):
        result = service.export(snapshot_id, format_name, path)
        print(format_name, [(item["path"], item["bytes"]) for item in result["files"]])


if __name__ == "__main__":
    main()
