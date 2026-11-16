from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.project_commands import CommandProjectStore

TOKEN = "assets-test-token"
AUTH = {"X-SEGYR-Token": TOKEN}


def test_assets_are_served_when_build_appears_after_app_creation(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    store = CommandProjectStore(root=tmp_path / "projects")
    app = create_app(TOKEN, dist_dir=dist, allow_test_host=True, project_store=store)
    client = TestClient(app)

    # The real incident: the backend was started before frontend/dist existed,
    # then the build appeared while the backend was already running.
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (assets / "index-test.js").write_text("console.log('ok');", encoding="utf-8")
    (assets / "index-test.css").write_text("body{color:red}", encoding="utf-8")
    (dist / "index.html").write_text(
        '<!doctype html><html><head>'
        '<meta name="segyr-session-token" content="__SEGYR_SESSION_TOKEN__">'
        '<script type="module" src="/assets/index-test.js"></script>'
        '<link rel="stylesheet" href="/assets/index-test.css">'
        '</head><body><div id="root">Chargement</div></body></html>',
        encoding="utf-8",
    )

    index = client.get("/")
    assert index.status_code == 200
    assert "__SEGYR_SESSION_TOKEN__" not in index.text

    javascript = client.get("/assets/index-test.js", headers=AUTH)
    assert javascript.status_code == 200, javascript.text
    assert javascript.headers["content-type"].startswith("text/javascript")

    stylesheet = client.get("/assets/index-test.css", headers=AUTH)
    assert stylesheet.status_code == 200, stylesheet.text
    assert stylesheet.headers["content-type"].startswith("text/css")

    assert re.search(r"/assets/index-test\.js\?v=[0-9a-f]+", index.text)
    assert re.search(r"/assets/index-test\.css\?v=[0-9a-f]+", index.text)

    missing = client.get("/assets/absent.js", headers=AUTH)
    assert missing.status_code == 404
    assert missing.headers["cache-control"] == "no-store"
