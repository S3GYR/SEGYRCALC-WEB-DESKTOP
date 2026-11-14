from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from backend.desktop import DialogAPI


def _fake_webview(result: object) -> SimpleNamespace:
    class Window:
        def create_file_dialog(self, *_args: object, **kwargs: object) -> object:
            self.kwargs = kwargs
            return result

    return SimpleNamespace(
        windows=[Window()],
        FileDialog=SimpleNamespace(OPEN=10, SAVE=30, FOLDER=20),
    )


def test_native_export_file_dialog_returns_absolute_spaced_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    expected = r"C:\Users\yoann\Desktop\Rapport avec espaces é.pdf"
    fake = _fake_webview((expected,))
    monkeypatch.setitem(sys.modules, "webview", fake)
    api = DialogAPI(tmp_path, tmp_path / "exports")
    selected = api.choose_export_file("pdf", "rapport-260013-rev5.pdf")
    assert selected == expected
    kwargs = fake.windows[0].kwargs
    assert kwargs["save_filename"] == "rapport-260013-rev5.pdf"
    assert str(kwargs["directory"]).endswith("exports\\native")


def test_native_export_dialog_cancel_returns_none(tmp_path: Path, monkeypatch) -> None:
    fake = _fake_webview(None)
    monkeypatch.setitem(sys.modules, "webview", fake)
    api = DialogAPI(tmp_path, tmp_path / "exports")
    assert api.choose_export_file("xlsx", "rapport.xlsx") is None
    assert api.choose_export_folder("csv") is None
