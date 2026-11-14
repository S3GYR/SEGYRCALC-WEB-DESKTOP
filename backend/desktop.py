"""Native Windows shell and qualification scenarios for WEB-02."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import secrets
import shutil
import threading
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any

import httpx
import uvicorn

from .main import create_app
from .project_store import DEFAULT_QUALIFICATION_ROOT
from .reporting import EXPORT_ROOT

TITLE = "SEGYRCALC - Bilan de puissance"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ICON = PROJECT_ROOT / "frontend" / "public" / "assets" / "segyrcalc.ico"


class DialogAPI:
    """Native Windows file dialogs exposed to the local pywebview page."""

    def __init__(self, root: Path, export_root: Path | None = None) -> None:
        self.root = root
        self.export_root = (export_root or EXPORT_ROOT).resolve()
        root.mkdir(parents=True, exist_ok=True)
        self.export_root.mkdir(parents=True, exist_ok=True)

    def choose_open_file(self) -> str | None:
        import webview

        window = webview.windows[0]
        result = window.create_file_dialog(
            webview.FileDialog.OPEN,
            directory=str(self.root),
            allow_multiple=False,
            file_types=("Projets SEGYRCALC (*.json)", "Tous les fichiers (*.*)"),
        )
        if not result:
            return None
        return str(result[0])

    def choose_save_file(self, default_name: str = "projet.segyrcalc-web.json") -> str | None:
        import webview

        name = (
            default_name
            if default_name.endswith(".segyrcalc-web.json")
            else f"{default_name}.segyrcalc-web.json"
        )
        window = webview.windows[0]
        result = window.create_file_dialog(
            webview.FileDialog.SAVE,
            directory=str(self.root),
            save_filename=name,
            file_types=("Projet WEB 03 (*.json)", "Tous les fichiers (*.*)"),
        )
        if not result:
            return None
        selected = str(result[0])
        if not selected.lower().endswith(".segyrcalc-web.json"):
            selected = f"{selected}.segyrcalc-web.json"
        return selected

    def choose_export_file(self, format_name: str, default_name: str = "rapport.pdf") -> str | None:
        import webview

        fmt = format_name.lower()
        if fmt not in {"pdf", "xlsx"}:
            return None
        suffix = f".{fmt}"
        name = default_name if default_name.lower().endswith(suffix) else f"{default_name}{suffix}"
        directory = self.export_root / "native"
        directory.mkdir(parents=True, exist_ok=True)
        label = "Rapport PDF (*.pdf)" if fmt == "pdf" else "Classeur Excel (*.xlsx)"
        window = webview.windows[0]
        result = window.create_file_dialog(
            webview.FileDialog.SAVE,
            directory=str(directory),
            save_filename=Path(name).name,
            file_types=(label, "Tous les fichiers (*.*)"),
        )
        if not result:
            return None
        selected = str(result[0])
        if not selected.lower().endswith(suffix):
            selected = f"{selected}{suffix}"
        return selected

    def choose_export_folder(self, default_name: str = "csv") -> str | None:
        import webview

        directory = self.export_root / "native"
        directory.mkdir(parents=True, exist_ok=True)
        start = directory
        candidate = directory / Path(default_name).name
        if candidate.is_dir():
            start = candidate
        window = webview.windows[0]
        result = window.create_file_dialog(
            webview.FileDialog.FOLDER,
            directory=str(start),
        )
        if not result:
            return None
        return str(result[0])


def _redacted_url(url: str) -> str:
    scheme, _, _rest = url.partition("://")
    return f"{scheme}://127.0.0.1:<port>/"


class ServerHandle:
    def __init__(self) -> None:
        self.token = secrets.token_urlsafe(32)
        self.app = create_app(self.token)
        self.server = uvicorn.Server(
            uvicorn.Config(
                self.app,
                host="127.0.0.1",
                port=0,
                log_level="warning",
                access_log=False,
                log_config=None,
                lifespan="off",
            )
        )
        self.thread = threading.Thread(target=self.server.run, name="segyr-local-api", daemon=True)
        self.port: int | None = None

    def start(self, timeout: float = 12.0) -> str:
        self.thread.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.server.started:
                break
            if not self.thread.is_alive():
                raise RuntimeError("Le service local s'est arrêté avant le démarrage.")
            time.sleep(0.05)
        else:
            raise TimeoutError("Le service local n'a pas démarré dans le délai imparti.")
        self.port = _bound_port(self.server)
        if self.port is None:
            raise RuntimeError("Port loopback introuvable.")
        return f"http://127.0.0.1:{self.port}/"

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if self.port is None:
            raise RuntimeError("Serveur non démarré.")
        headers = {"X-SEGYR-Token": self.token}
        return httpx.request(
            method,
            f"http://127.0.0.1:{self.port}{path}",
            headers=headers,
            timeout=10,
            **kwargs,
        )


def _bound_port(server: uvicorn.Server) -> int | None:
    try:
        sockets = server.servers[0].sockets
        if not sockets:
            return None
        return int(sockets[0].getsockname()[1])
    except (AttributeError, IndexError, OSError):
        return None


def _window_handle(title: str) -> int | None:
    hwnd = ctypes.windll.user32.FindWindowW(None, title)
    return int(hwnd) if hwnd else None


def _window_rect(title: str) -> tuple[int, int, int, int] | None:
    user32 = ctypes.windll.user32
    hwnd = _window_handle(title)
    if not hwnd:
        return None
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return rect.left, rect.top, rect.right, rect.bottom


def _bring_to_front(title: str) -> None:
    user32 = ctypes.windll.user32
    hwnd = _window_handle(title)
    if not hwnd:
        return
    user32.ShowWindow(hwnd, 9)
    user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    user32.SetFocus(hwnd)
    time.sleep(0.5)
    user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)


def capture_window(title: str, destination: Path, *, attempts: int = 40) -> bool:
    from PIL import ImageGrab

    for _ in range(attempts):
        rect = _window_rect(title)
        if rect:
            _bring_to_front(title)
            time.sleep(0.7)
            rect = _window_rect(title)
            if rect:
                left, top, right, bottom = rect
                if right > left and bottom > top:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True).save(
                        destination
                    )
                    return True
        time.sleep(0.25)
    return False


def _click(window: Any, test_id: str) -> None:
    window.evaluate_js(f"document.querySelector('[data-testid=\"{test_id}\"]')?.click();")


def _set_value(window: Any, test_id: str, value: str, event: str = "input") -> None:
    escaped = json.dumps(value, ensure_ascii=False)
    window.evaluate_js(
        "(() => {"
        f"const el=document.querySelector('[data-testid=\"{test_id}\"]');"
        "if(!el) return;"
        "const proto = el.tagName === 'SELECT' ? window.HTMLSelectElement.prototype "
        ": (el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype "
        ": window.HTMLInputElement.prototype);"
        "const setter=Object.getOwnPropertyDescriptor(proto,'value').set;"
        f"setter.call(el,{escaped});"
        f"el.dispatchEvent(new Event('{event}',{{bubbles:true}}));"
        "el.dispatchEvent(new Event('change',{bubbles:true}));"
        "})();"
    )


def _capture(window: Any, directory: Path, name: str) -> dict[str, Any]:
    destination = directory / name
    ok = capture_window(TITLE, destination)
    print(json.dumps({"event": "capture", "path": str(destination), "ok": ok}))
    return {"name": name, "path": str(destination), "ok": ok}


def run_screens(window: Any, directory: Path) -> list[dict[str, Any]]:
    captures: list[dict[str, Any]] = []
    screens = [
        ("dashboard", "01-accueil.png"),
        ("projects", "02-projets.png"),
        ("architecture", "03-architecture.png"),
        ("balance", "04-bilan-puissance.png"),
    ]
    for screen, name in screens:
        _click(window, f"nav-{screen}")
        time.sleep(0.9)
        captures.append(_capture(window, directory, name))

    _click(window, "balance-tab-loads")
    time.sleep(0.5)
    _click(window, "row-load-REC-01")
    time.sleep(0.7)
    captures.append(_capture(window, directory, "05-proprietes.png"))

    _click(window, "nav-engine")
    time.sleep(0.8)
    captures.append(_capture(window, directory, "06-calcul-formulaire.png"))
    _click(window, "engine-run")
    time.sleep(1.0)
    captures.append(_capture(window, directory, "07-calcul-resultat.png"))
    _click(window, "engine-run-error")
    time.sleep(1.0)
    captures.append(_capture(window, directory, "08-erreur.png"))

    _click(window, "nav-settings")
    time.sleep(0.8)
    captures.append(_capture(window, directory, "09-parametres.png"))
    return captures


def run_interactions(window: Any, directory: Path) -> list[dict[str, Any]]:
    captures: list[dict[str, Any]] = []
    _click(window, "nav-balance")
    time.sleep(0.8)
    _set_value(window, "balance-search", "atelier")
    time.sleep(0.5)
    _click(window, "sort-p_after_ks_w")
    time.sleep(0.5)
    _click(window, "row-DEP-06")
    time.sleep(0.7)
    captures.append(_capture(window, directory, "10-recherche-tri-selection.png"))

    _click(window, "nav-architecture")
    time.sleep(0.7)
    _set_value(window, "architecture-search", "bureaux")
    time.sleep(0.5)
    _click(window, "tree-load-REC-01")
    time.sleep(0.7)
    captures.append(_capture(window, directory, "11-architecture-recherche.png"))

    _click(window, "nav-projects")
    time.sleep(0.7)
    _click(window, "projects-tab-demo")
    time.sleep(0.5)
    captures.append(_capture(window, directory, "12-projets-demo.png"))
    return captures


def _undo(window: Any) -> None:
    window.evaluate_js(
        "window.dispatchEvent(new KeyboardEvent('keydown',{key:'z',ctrlKey:true,bubbles:true}))"
    )


def _redo(window: Any) -> None:
    window.evaluate_js(
        "window.dispatchEvent(new KeyboardEvent('keydown',{key:'y',ctrlKey:true,bubbles:true}))"
    )


def _click_by_text(window: Any, selector: str, text: str) -> None:
    window.evaluate_js(
        "(() => {"
        f"const nodes=Array.from(document.querySelectorAll({json.dumps(selector)}));"
        f"const target=nodes.find(x=>(x.textContent||'').includes({json.dumps(text)}));"
        "target?.click();"
        "return Boolean(target);"
        "})();"
    )


def run_project_cycle(
    window: Any,
    directory: Path,
    qualification_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    captures: list[dict[str, Any]] = []
    target = qualification_root / "web03-native-qualification.segyrcalc-web.json"
    target.unlink(missing_ok=True)
    target.with_name(target.name + ".bak").unlink(missing_ok=True)

    _click(window, "nav-projects")
    time.sleep(0.8)
    _click(window, "project-new")
    time.sleep(0.5)
    _set_value(window, "project-name", "Projet natif WEB-03")
    _set_value(window, "project-reference", "WEB03-NATIF")
    _set_value(window, "project-client", "SEGYR Technologies")
    _set_value(window, "project-site", "Site natif")
    _set_value(window, "project-address", "3 rue de la Qualification")
    _set_value(window, "project-author", "Qualification Windows")
    _set_value(window, "project-observations", "Cycle natif création → sauvegarde → réouverture")
    _click_by_text(window, ".form-modal-foot button", "Créer le projet")
    time.sleep(1.2)
    captures.append(_capture(window, directory, "15-creation-projet.png"))

    _click(window, "add-board")
    time.sleep(0.4)
    _set_value(window, "entity-designation", "Tableau divisionnaire natif")
    _click_by_text(window, ".form-modal-foot button", "Valider")
    time.sleep(0.9)

    _click_by_text(window, ".tree-panel button", "Tableau divisionnaire natif")
    time.sleep(0.4)
    _click(window, "add-feeder")
    time.sleep(0.4)
    _set_value(window, "entity-designation", "Départ natif")
    _set_value(window, "entity-ks", "0.9")
    _click_by_text(window, ".form-modal-foot button", "Valider")
    time.sleep(0.9)

    _click_by_text(window, ".tree-panel button", "Départ natif")
    time.sleep(0.4)
    _click(window, "add-load")
    time.sleep(0.4)
    _set_value(window, "entity-designation", "Récepteur natif")
    _set_value(window, "entity-network", "TRI")
    _set_value(window, "entity-voltage", "400")
    _set_value(window, "entity-power", "5000")
    _set_value(window, "entity-quantity", "2")
    _set_value(window, "entity-pf", "0.9")
    _set_value(window, "entity-ku", "0.8")
    _click_by_text(window, ".form-modal-foot button", "Valider")
    time.sleep(1.2)
    captures.append(_capture(window, directory, "16-architecture-editee.png"))

    _click(window, "nav-projects")
    time.sleep(0.8)
    _click(window, "project-save")
    time.sleep(0.5)
    _set_value(window, "path-input", str(target))
    _click_by_text(window, ".form-modal-foot button", "Enregistrer")
    time.sleep(1.4)
    captures.append(_capture(window, directory, "17-projet-enregistre.png"))

    _click(window, "project-close")
    time.sleep(0.9)
    captures.append(_capture(window, directory, "18-projet-ferme.png"))

    _click(window, "open-file-web03-native-qualification.segyrcalc-web.json")
    time.sleep(1.4)
    captures.append(_capture(window, directory, "19-projet-reouvert.png"))

    _click(window, "nav-balance")
    time.sleep(1.0)
    captures.append(_capture(window, directory, "20-bilan-reouvert.png"))

    body = window.evaluate_js("document.body.innerText") or ""
    checks = {
        "project_reference": "WEB03-NATIF" in body,
        "receiver_visible": "Récepteur natif" in body,
        "saved": "Enregistré" in body,
        "file_exists": target.is_file(),
        "file_bytes": target.stat().st_size if target.is_file() else 0,
    }
    if target.is_file():
        envelope = json.loads(target.read_text(encoding="utf-8"))
        checks["schema"] = envelope.get("schema")
        checks["schema_version"] = envelope.get("schema_version")
        checks["embedded_project_id"] = (
            envelope.get("calcelect_v14", {})
            .get("project", {})
            .get("electrical", {})
            .get("project_id")
        )
    print(json.dumps({"event": "project_cycle_checks", **checks}, ensure_ascii=False))
    return captures, checks


def _visible_window_titles() -> list[tuple[int, str]]:
    user32 = ctypes.windll.user32
    windows: list[tuple[int, str]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        windows.append((int(hwnd), buffer.value))
        return True

    user32.EnumWindows(callback, 0)
    return windows


def run_native_dialog(window: Any, directory: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from PIL import ImageGrab

    captures: list[dict[str, Any]] = []
    _click(window, "nav-projects")
    time.sleep(0.9)
    _click(window, "project-open")
    time.sleep(2.5)
    windows = _visible_window_titles()
    titles = [
        title
        for _hwnd, title in windows
        if "Ouvrir" in title or "Open" in title or "SEGYRCALC" in title
    ]
    candidate = next(
        ((hwnd, title) for hwnd, title in windows if "Ouvrir" in title or "Open" in title),
        None,
    )
    found = candidate is not None
    destination = directory / "21-dialogue-natif.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if candidate is not None:
        ctypes.windll.user32.SetForegroundWindow(candidate[0])
        time.sleep(0.5)
        captured = capture_window(candidate[1], destination)
    else:
        ImageGrab.grab(all_screens=True).save(destination)
        captured = True
    captures.append({"name": destination.name, "path": str(destination), "ok": captured})
    if candidate is not None:
        ctypes.windll.user32.PostMessageW(candidate[0], 0x0010, 0, 0)
    else:
        ctypes.windll.user32.keybd_event(0x1B, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x1B, 0, 2, 0)
    time.sleep(1.0)
    print(
        json.dumps({"event": "native_dialog", "found": found, "titles": titles}, ensure_ascii=True)
    )
    return captures, {"dialog_found": found, "window_titles": titles, "capture": str(destination)}


def run_web04_cycle(
    window: Any,
    directory: Path,
    qualification_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    captures: list[dict[str, Any]] = []
    target = qualification_root / "web04-native-qualification.segyrcalc-web.json"
    target.unlink(missing_ok=True)
    target.with_name(target.name + ".bak").unlink(missing_ok=True)

    _click(window, "nav-projects")
    time.sleep(0.8)
    _click(window, "project-new")
    time.sleep(0.5)
    _set_value(window, "project-name", "Projet natif WEB-04")
    _set_value(window, "project-reference", "WEB04-NATIF")
    _set_value(window, "project-client", "SEGYR Technologies")
    _set_value(window, "project-site", "Site natif WEB-04")
    _set_value(window, "project-address", "4 rue de la Transaction")
    _set_value(window, "project-author", "Qualification Windows")
    _set_value(window, "project-observations", "Cycle architecture avancée WEB-04")
    _click_by_text(window, ".form-modal-foot button", "Créer le projet")
    time.sleep(1.2)
    captures.append(_capture(window, directory, "01-creation-projet.png"))

    _click(window, "add-board")
    time.sleep(0.4)
    _set_value(window, "entity-designation", "Tableau WEB-04 natif")
    _click_by_text(window, ".form-modal-foot button", "Valider")
    time.sleep(0.9)

    _click_by_text(window, ".tree-panel button", "Tableau WEB-04 natif")
    time.sleep(0.3)
    _click(window, "add-feeder")
    time.sleep(0.4)
    _set_value(window, "entity-designation", "Départ A natif")
    _set_value(window, "entity-ks", "0.9")
    _click_by_text(window, ".form-modal-foot button", "Valider")
    time.sleep(0.9)

    _click_by_text(window, ".tree-panel button", "Tableau WEB-04 natif")
    time.sleep(0.3)
    _click(window, "add-feeder")
    time.sleep(0.4)
    _set_value(window, "entity-designation", "Départ B natif")
    _set_value(window, "entity-ks", "0.9")
    _click_by_text(window, ".form-modal-foot button", "Valider")
    time.sleep(0.9)

    _click_by_text(window, ".tree-panel button", "Départ A natif")
    time.sleep(0.3)
    _click(window, "add-load")
    time.sleep(0.4)
    _set_value(window, "entity-designation", "Récepteur A natif")
    _set_value(window, "entity-network", "TRI")
    _set_value(window, "entity-voltage", "400")
    _set_value(window, "entity-power", "4000")
    _set_value(window, "entity-quantity", "1")
    _set_value(window, "entity-pf", "0.9")
    _set_value(window, "entity-ku", "0.8")
    _click_by_text(window, ".form-modal-foot button", "Valider")
    time.sleep(1.0)

    _click_by_text(window, ".tree-panel button", "Départ A natif")
    time.sleep(0.3)
    _click(window, "add-load")
    time.sleep(0.4)
    _set_value(window, "entity-designation", "Récepteur B natif")
    _set_value(window, "entity-network", "TRI")
    _set_value(window, "entity-voltage", "400")
    _set_value(window, "entity-power", "2000")
    _set_value(window, "entity-quantity", "1")
    _set_value(window, "entity-pf", "0.9")
    _set_value(window, "entity-ku", "0.8")
    _click_by_text(window, ".form-modal-foot button", "Valider")
    time.sleep(1.0)
    captures.append(_capture(window, directory, "02-architecture-initiale.png"))

    _click_by_text(window, ".tree-panel button", "Départ A natif")
    time.sleep(0.3)
    _click(window, "duplicate-entity")
    time.sleep(0.5)
    _click_by_text(window, ".form-modal-foot button", "Dupliquer")
    time.sleep(1.2)
    captures.append(_capture(window, directory, "03-depart-duplique.png"))

    _click_by_text(window, ".tree-panel button", "Récepteur A natif")
    time.sleep(0.3)
    _click(window, "move-entity")
    time.sleep(0.5)
    _set_value(window, "destination-select", "DEP-03", "change")
    _click_by_text(window, ".form-modal-foot button", "Déplacer")
    time.sleep(1.2)
    captures.append(_capture(window, directory, "04-recepteur-deplace.png"))

    _click_by_text(window, ".tree-panel button", "Récepteur A natif")
    time.sleep(0.3)
    _click(window, "edit-entity")
    time.sleep(0.5)
    _set_value(window, "entity-power", "7000")
    _click_by_text(window, ".form-modal-foot button", "Valider")
    time.sleep(1.2)
    captures.append(_capture(window, directory, "05-modification-puissance.png"))

    _click(window, "undo-entity")
    time.sleep(1.2)
    captures.append(_capture(window, directory, "06-annulation.png"))
    _click(window, "redo-entity")
    time.sleep(1.2)
    captures.append(_capture(window, directory, "07-retablissement.png"))

    _click_by_text(window, ".tree-panel button", "Départ B natif")
    time.sleep(0.3)
    _click(window, "delete-entity")
    time.sleep(0.6)
    captures.append(_capture(window, directory, "08-confirmation-suppression.png"))
    _click_by_text(window, ".confirm-dialog button", "Supprimer avec confirmation")
    time.sleep(1.2)
    captures.append(_capture(window, directory, "09-suppression-appliquee.png"))
    _click(window, "undo-entity")
    time.sleep(1.2)
    captures.append(_capture(window, directory, "10-suppression-annulee.png"))

    _click(window, "nav-projects")
    time.sleep(0.8)
    _click(window, "project-save")
    time.sleep(0.5)
    _set_value(window, "path-input", str(target))
    _click_by_text(window, ".form-modal-foot button", "Enregistrer")
    time.sleep(1.4)
    captures.append(_capture(window, directory, "11-projet-enregistre.png"))

    _click(window, "project-close")
    time.sleep(0.9)
    _click(window, "open-file-web04-native-qualification.segyrcalc-web.json")
    time.sleep(1.4)
    captures.append(_capture(window, directory, "12-projet-reouvert.png"))
    _click(window, "nav-balance")
    time.sleep(1.0)
    captures.append(_capture(window, directory, "13-bilan-reouvert.png"))

    body = window.evaluate_js("document.body.innerText") or ""
    checks = {
        "project_reference": "WEB04-NATIF" in body,
        "receiver_visible": "Récepteur A natif" in body,
        "saved": "Enregistré" in body,
        "file_exists": target.is_file(),
        "file_bytes": target.stat().st_size if target.is_file() else 0,
        "total_15kw": "15,00 kW" in body or "15.00 kW" in body,
    }
    if target.is_file():
        envelope = json.loads(target.read_text(encoding="utf-8"))
        checks["schema"] = envelope.get("schema")
        checks["schema_version"] = envelope.get("schema_version")
        checks["embedded_project_id"] = (
            envelope.get("calcelect_v14", {})
            .get("project", {})
            .get("electrical", {})
            .get("project_id")
        )
    print(json.dumps({"event": "web04_cycle_checks", **checks}, ensure_ascii=True))
    return captures, checks


def run_power_balance_05(
    window: Any,
    directory: Path,
    qualification_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    captures: list[dict[str, Any]] = []
    target = qualification_root / "web05-native-qualification.segyrcalc-web.json"
    target.unlink(missing_ok=True)
    target.with_name(target.name + ".bak").unlink(missing_ok=True)

    _click(window, "nav-projects")
    time.sleep(0.8)
    _click(window, "project-new")
    time.sleep(0.5)
    _set_value(window, "project-name", "Bilan natif WEB-05")
    _set_value(window, "project-reference", "WEB05-NATIF")
    _set_value(window, "project-client", "SEGYR Technologies")
    _set_value(window, "project-site", "Site bilan natif")
    _set_value(window, "project-address", "5 rue du Bilan")
    _set_value(window, "project-author", "Qualification Windows")
    _set_value(window, "project-observations", "Cycle bilan de puissance WEB-05")
    _click_by_text(window, ".form-modal-foot button", "Créer le projet")
    time.sleep(1.2)
    captures.append(_capture(window, directory, "01-creation-projet.png"))

    _click(window, "add-board")
    time.sleep(0.4)
    _set_value(window, "entity-designation", "Tableau A")
    _click_by_text(window, ".form-modal-foot button", "Valider")
    time.sleep(0.9)
    _click(window, "add-board")
    time.sleep(0.4)
    _set_value(window, "entity-designation", "Tableau B")
    _click_by_text(window, ".form-modal-foot button", "Valider")
    time.sleep(0.9)

    _click_by_text(window, ".tree-panel button", "Tableau A")
    time.sleep(0.3)
    _click(window, "add-feeder")
    time.sleep(0.4)
    _set_value(window, "entity-designation", "Départ A")
    _set_value(window, "entity-ks", "0.9")
    _click_by_text(window, ".form-modal-foot button", "Valider")
    time.sleep(0.9)
    _click_by_text(window, ".tree-panel button", "Tableau A")
    time.sleep(0.3)
    _click(window, "add-feeder")
    time.sleep(0.4)
    _set_value(window, "entity-designation", "Départ B")
    _set_value(window, "entity-ks", "0.8")
    _click_by_text(window, ".form-modal-foot button", "Valider")
    time.sleep(0.9)
    _click_by_text(window, ".tree-panel button", "Tableau B")
    time.sleep(0.3)
    _click(window, "add-feeder")
    time.sleep(0.4)
    _set_value(window, "entity-designation", "Départ C")
    _set_value(window, "entity-ks", "0.85")
    _click_by_text(window, ".form-modal-foot button", "Valider")
    time.sleep(0.9)

    def add_load(
        feeder: str,
        designation: str,
        network: str,
        voltage: str,
        power: str,
        quantity: str,
        phase: str,
        ku: str,
    ) -> None:
        _click_by_text(window, ".tree-panel button", feeder)
        time.sleep(0.3)
        _click(window, "add-load")
        time.sleep(0.4)
        _set_value(window, "entity-designation", designation)
        _set_value(window, "entity-network", network, "change")
        _set_value(window, "entity-voltage", voltage)
        _set_value(window, "entity-power", power)
        _set_value(window, "entity-quantity", quantity)
        _set_value(window, "entity-pf", "0.9")
        _set_value(window, "entity-ku", ku)
        if phase:
            _set_value(window, "entity-phase", phase, "change")
        _click_by_text(window, ".form-modal-foot button", "Valider")
        time.sleep(1.0)

    add_load("Départ A", "Éclairage A", "MONO", "230", "1000", "4", "L1", "0.8")
    add_load("Départ A", "Éclairage B", "MONO", "230", "800", "3", "L2", "0.7")
    add_load("Départ B", "Moteur C", "TRI", "400", "5000", "2", "", "0.9")
    add_load("Départ C", "Moteur D", "TRI", "400", "3000", "1", "", "0.9")

    _click(window, "nav-balance")
    time.sleep(1.2)
    captures.append(_capture(window, directory, "02-bilan-recepteurs.png"))
    _click(window, "balance-tab-feeders")
    time.sleep(0.7)
    captures.append(_capture(window, directory, "03-bilan-departs.png"))
    _click(window, "balance-tab-boards")
    time.sleep(0.7)
    captures.append(_capture(window, directory, "04-bilan-tableaux.png"))
    _click(window, "balance-tab-tgbt")
    time.sleep(0.7)
    captures.append(_capture(window, directory, "05-bilan-tgbt.png"))
    window.evaluate_js(
        "document.querySelector('[data-testid=\"phase-balance-panel\"]')?.scrollIntoView({block:'center'})"
    )
    time.sleep(0.7)
    captures.append(_capture(window, directory, "05b-phases.png"))
    window.evaluate_js("window.scrollTo(0,0)")
    _click(window, "balance-tab-loads")
    time.sleep(0.6)

    _click_by_text(window, '[data-testid^="row-load-"]', "Éclairage A")
    time.sleep(0.5)
    _set_value(window, "coefficient-input", "0.5")
    _click(window, "coefficient-apply")
    time.sleep(1.2)
    captures.append(_capture(window, directory, "06-ku-modifie-comparaison.png"))
    window.evaluate_js(
        "document.querySelector('[data-testid=\"comparison-panel\"]')?.scrollIntoView({block:'center'})"
    )
    time.sleep(0.7)
    captures.append(_capture(window, directory, "06b-comparaison-ku.png"))
    window.evaluate_js("window.scrollTo(0,0)")

    _undo(window)
    time.sleep(1.2)
    captures.append(_capture(window, directory, "07-annulation-ku.png"))
    _redo(window)
    time.sleep(1.2)
    captures.append(_capture(window, directory, "08-retablissement-ku.png"))

    _click(window, "nav-architecture")
    time.sleep(0.8)
    _click_by_text(window, ".tree-panel button", "Éclairage A")
    time.sleep(0.4)
    _click(window, "edit-entity")
    time.sleep(0.5)
    _set_value(window, "entity-power", "1200")
    _click_by_text(window, ".form-modal-foot button", "Valider")
    time.sleep(1.2)
    _click(window, "nav-balance")
    time.sleep(1.0)
    captures.append(_capture(window, directory, "09-puissance-modifiee-comparaison.png"))
    comparison_seen = "Avant / après" in (window.evaluate_js("document.body.innerText") or "")
    window.evaluate_js(
        "document.querySelector('[data-testid=\"comparison-panel\"]')?.scrollIntoView({block:'center'})"
    )
    time.sleep(0.7)
    captures.append(_capture(window, directory, "09b-comparaison-puissance.png"))
    window.evaluate_js("window.scrollTo(0,0)")
    _undo(window)
    time.sleep(1.2)
    captures.append(_capture(window, directory, "10-annulation-puissance.png"))
    _redo(window)
    time.sleep(1.2)
    captures.append(_capture(window, directory, "11-retablissement-puissance.png"))

    _click(window, "nav-projects")
    time.sleep(0.8)
    _click(window, "project-save")
    time.sleep(0.5)
    _set_value(window, "path-input", str(target))
    _click_by_text(window, ".form-modal-foot button", "Enregistrer")
    time.sleep(1.4)
    captures.append(_capture(window, directory, "12-projet-enregistre.png"))
    _click(window, "project-close")
    time.sleep(0.9)
    _click(window, "open-file-web05-native-qualification.segyrcalc-web.json")
    time.sleep(1.5)
    captures.append(_capture(window, directory, "13-projet-reouvert.png"))
    _click(window, "nav-balance")
    time.sleep(1.0)
    captures.append(_capture(window, directory, "14-bilan-final.png"))

    body = window.evaluate_js("document.body.innerText") or ""
    checks = {
        "project_reference": "WEB05-NATIF" in body,
        "receiver_visible": "Éclairage A" in body,
        "saved": "Enregistré" in body,
        "file_exists": target.is_file(),
        "file_bytes": target.stat().st_size if target.is_file() else 0,
        "traceability": "Traçabilité" in body,
        "comparison_seen": comparison_seen,
        "tgbt": "TGBT" in body,
    }
    if target.is_file():
        envelope = json.loads(target.read_text(encoding="utf-8"))
        checks["schema"] = envelope.get("schema")
        checks["schema_version"] = envelope.get("schema_version")
        checks["embedded_project_id"] = (
            envelope.get("calcelect_v14", {})
            .get("project", {})
            .get("electrical", {})
            .get("project_id")
        )
    print(json.dumps({"event": "power_balance_05_checks", **checks}, ensure_ascii=True))
    return captures, checks


def _verify_report_exports(
    pdf_path: Path, xlsx_path: Path, csv_dir: Path, capture_dir: Path
) -> dict[str, Any]:
    from openpyxl import load_workbook

    try:
        from pypdf import PdfReader
    except ImportError:
        PdfReader = None  # type: ignore[assignment,misc]

    checks: dict[str, Any] = {
        "pdf_exists": pdf_path.is_file(),
        "pdf_bytes": pdf_path.stat().st_size if pdf_path.is_file() else 0,
        "xlsx_exists": xlsx_path.is_file(),
        "xlsx_bytes": xlsx_path.stat().st_size if xlsx_path.is_file() else 0,
        "csv_dir_exists": csv_dir.is_dir(),
    }
    if pdf_path.is_file() and PdfReader is not None:
        reader = PdfReader(str(pdf_path))
        checks["pdf_pages"] = len(reader.pages)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        checks["pdf_text_project"] = "WEB05-NATIF" in text
        checks["pdf_text_title"] = "Bilan de puissance" in text
        checks["pdf_text_accents"] = "Récepteurs" in text or "Récepteur" in text
        try:
            import pymupdf as fitz
        except ImportError:
            fitz = None  # type: ignore[assignment,misc]
        if fitz is not None:
            document = fitz.open(str(pdf_path))
            if document.page_count:
                first = capture_dir / "pdf-page-01.png"
                last = capture_dir / "pdf-page-last.png"
                document[0].get_pixmap(dpi=110).save(str(first))
                document[document.page_count - 1].get_pixmap(dpi=110).save(str(last))
                checks["pdf_render_first"] = str(first)
                checks["pdf_render_last"] = str(last)
                if document.page_count > 2:
                    middle = capture_dir / "pdf-page-middle.png"
                    document[document.page_count // 2].get_pixmap(dpi=110).save(str(middle))
                    checks["pdf_render_middle"] = str(middle)
            document.close()
    if xlsx_path.is_file():
        workbook = load_workbook(xlsx_path, data_only=False, read_only=False)
        checks["xlsx_sheets"] = workbook.sheetnames
        checks["xlsx_sheet_count"] = len(workbook.sheetnames)
        checks["xlsx_rows"] = {name: workbook[name].max_row for name in workbook.sheetnames}
        formulas = 0
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.data_type == "f":
                        formulas += 1
        checks["xlsx_formula_cells"] = formulas
        checks["xlsx_external_links"] = len(getattr(workbook, "_external_links", []))
        workbook.close()
    if csv_dir.is_dir():
        csv_files = sorted(csv_dir.glob("*.csv"))
        checks["csv_files"] = [item.name for item in csv_files]
        checks["csv_count"] = len(csv_files)
        if csv_files:
            first = csv_files[0]
            raw = first.read_bytes()
            checks["csv_bom"] = raw.startswith(b"\xef\xbb\xbf")
            text = raw.decode("utf-8-sig")
            checks["csv_semicolon"] = ";" in text.splitlines()[0]
            checks["csv_crlf"] = "\r\n" in text
    return checks


def run_reporting_06(
    window: Any,
    directory: Path,
    qualification_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    captures: list[dict[str, Any]] = []
    source = Path(
        os.environ.get(
            "SEGYR_SAMPLE_PROJECT",
            str(
                PROJECT_ROOT
                / "packaging"
                / "sample_projects"
                / "web05-native-qualification.segyrcalc-web.json"
            ),
        )
    )
    target = qualification_root / "web06-native-web05-import.segyrcalc-web.json"
    if source.is_file() and not target.is_file():
        shutil.copy2(source, target)
    export_dir = EXPORT_ROOT / "native"
    export_dir.mkdir(parents=True, exist_ok=True)
    pdf_before = export_dir / "web06-rapport-avant-ku.pdf"
    pdf_after = export_dir / "web06-rapport-apres-ku.pdf"
    xlsx_path = export_dir / "web06-rapport.xlsx"
    csv_dir = export_dir / "web06-csv"
    for path in (pdf_before, pdf_after, xlsx_path):
        path.unlink(missing_ok=True)
    if csv_dir.is_dir():
        shutil.rmtree(csv_dir)

    _click(window, "nav-projects")
    time.sleep(0.9)
    _click(window, "project-open")
    time.sleep(0.7)
    _set_value(window, "path-input", str(target))
    _click_by_text(window, ".form-modal-foot button", "Ouvrir")
    time.sleep(1.5)
    captures.append(_capture(window, directory, "01-projet-web05-ouvert.png"))

    _click(window, "nav-balance")
    time.sleep(1.1)
    captures.append(_capture(window, directory, "02-bilan-web05-verifie.png"))

    _click(window, "nav-reports")
    time.sleep(1.0)
    captures.append(_capture(window, directory, "03-module-rapports.png"))
    _click(window, "report-preview-generate")
    time.sleep(1.5)
    captures.append(_capture(window, directory, "04-apercu-rapport.png"))
    window.evaluate_js(
        "document.querySelector('[data-testid=\"report-table-receivers\"]')?.scrollIntoView({block:'start'})"
    )
    time.sleep(0.8)
    captures.append(_capture(window, directory, "04b-bilan-recepteurs-s-i.png"))
    window.evaluate_js("window.scrollTo(0,0)")
    time.sleep(0.4)

    _click(window, "report-export-pdf")
    time.sleep(0.7)
    _set_value(window, "export-path-input", str(pdf_before))
    _click_by_text(window, ".form-modal-foot button", "Exporter")
    time.sleep(2.0)
    captures.append(_capture(window, directory, "05-export-pdf.png"))

    _click(window, "report-export-xlsx")
    time.sleep(0.7)
    _set_value(window, "export-path-input", str(xlsx_path))
    _click_by_text(window, ".form-modal-foot button", "Exporter")
    time.sleep(1.6)
    captures.append(_capture(window, directory, "06-export-xlsx.png"))

    _click(window, "report-export-csv")
    time.sleep(0.7)
    _set_value(window, "export-path-input", str(csv_dir))
    _click_by_text(window, ".form-modal-foot button", "Exporter")
    time.sleep(1.4)
    captures.append(_capture(window, directory, "07-export-csv.png"))

    before_checks = _verify_report_exports(pdf_before, xlsx_path, csv_dir, directory)
    before_text = (
        window.evaluate_js(
            "document.querySelector('[data-testid=\"report-preview\"]')?.innerText || ''"
        )
        or ""
    )
    signatures = (
        "(() => Array.from(document.querySelectorAll('.report-summary-grid .summary-card strong'))"
        ".map(item => item.textContent || '').join('|'))()"
    )
    before_signature = window.evaluate_js(signatures) or ""

    _click(window, "nav-balance")
    time.sleep(0.9)
    _click(window, "balance-tab-loads")
    time.sleep(0.5)
    _click_by_text(window, '[data-testid^="row-load-"]', "Éclairage A")
    time.sleep(0.4)
    _set_value(window, "coefficient-input", "0.3")
    _click(window, "coefficient-apply")
    time.sleep(1.4)
    captures.append(_capture(window, directory, "08-ku-modifie.png"))

    _click(window, "nav-reports")
    time.sleep(0.8)
    _click(window, "report-preview-generate")
    time.sleep(1.4)
    captures.append(_capture(window, directory, "09-apercu-apres-ku.png"))
    after_signature = window.evaluate_js(signatures) or ""
    _click(window, "report-export-pdf")
    time.sleep(0.7)
    _set_value(window, "export-path-input", str(pdf_after))
    _click_by_text(window, ".form-modal-foot button", "Exporter")
    time.sleep(2.0)
    captures.append(_capture(window, directory, "10-pdf-apres-ku.png"))
    after_checks = _verify_report_exports(pdf_after, xlsx_path, csv_dir, directory)

    _undo(window)
    time.sleep(1.3)
    _click(window, "nav-reports")
    time.sleep(0.7)
    _click(window, "report-preview-generate")
    time.sleep(1.2)
    undo_signature = window.evaluate_js(signatures) or ""
    captures.append(_capture(window, directory, "11-annulation-verifiee.png"))

    _click(window, "nav-projects")
    time.sleep(0.8)
    _click(window, "project-save")
    time.sleep(0.6)
    _set_value(window, "path-input", str(target))
    _click_by_text(window, ".form-modal-foot button", "Enregistrer")
    time.sleep(1.3)
    _click(window, "project-close")
    time.sleep(0.9)
    _click(window, "project-open")
    time.sleep(0.6)
    _set_value(window, "path-input", str(target))
    _click_by_text(window, ".form-modal-foot button", "Ouvrir")
    time.sleep(1.5)
    _click(window, "nav-balance")
    time.sleep(1.0)
    captures.append(_capture(window, directory, "12-projet-reouvert.png"))
    _click(window, "nav-reports")
    time.sleep(0.8)
    _click(window, "report-preview-generate")
    time.sleep(1.3)
    captures.append(_capture(window, directory, "13-rapport-final.png"))

    checks = {
        "project_reference": "WEB05-NATIF" in (window.evaluate_js("document.body.innerText") or ""),
        "receiver_visible": "Éclairage A" in (window.evaluate_js("document.body.innerText") or ""),
        "reports_preview": bool(before_text),
        "comparison_before_after": bool(before_signature) and before_signature != after_signature,
        "undo_restored": bool(undo_signature) and undo_signature == before_signature,
        "before_summary": before_signature,
        "after_summary": after_signature,
        "undo_summary": undo_signature,
        "project_saved": target.is_file(),
        "schema": None,
        "project_id": None,
        **{f"before_{key}": value for key, value in before_checks.items()},
        **{f"after_{key}": value for key, value in after_checks.items()},
    }
    if target.is_file():
        envelope = json.loads(target.read_text(encoding="utf-8"))
        checks["schema"] = envelope.get("schema")
        checks["schema_version"] = envelope.get("schema_version")
        checks["project_id"] = (
            envelope.get("calcelect_v14", {})
            .get("project", {})
            .get("electrical", {})
            .get("project_id")
        )
    print(json.dumps({"event": "reporting_06_checks", **checks}, ensure_ascii=True))
    return captures, checks


def run_resize(window: Any, directory: Path) -> list[dict[str, Any]]:
    captures: list[dict[str, Any]] = []
    _click(window, "nav-balance")
    time.sleep(0.8)
    window.resize(1366, 768)
    time.sleep(0.8)
    captures.append(_capture(window, directory, "13-resize-1366x768.png"))
    window.resize(1280, 720)
    time.sleep(0.8)
    captures.append(_capture(window, directory, "14-resize-1280x720.png"))
    window.resize(1360, 860)
    time.sleep(0.8)
    return captures


def run_native(
    url: str,
    *,
    capture: Path | None,
    capture_dir: Path | None,
    auto_close: float | None,
    scenario: str | None,
) -> int:
    import webview

    started = time.perf_counter()
    runtime_path = os.environ.get("SEGYR_WEBVIEW2_RUNTIME")
    if runtime_path:
        webview.settings["WEBVIEW2_RUNTIME_PATH"] = runtime_path
    result: dict[str, Any] = {
        "window": False,
        "capture": False,
        "title": TITLE,
        "scenario": scenario,
        "webview2_runtime_path": runtime_path or "system",
    }
    closed = threading.Event()
    if scenario in {"project-cycle", "web04-cycle", "power-balance-05", "reporting-06"}:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}native_dialogs=0"
    window = webview.create_window(
        TITLE,
        url,
        width=1360,
        height=860,
        min_size=(1180, 720),
        background_color="#F2F5F8",
        text_select=True,
        on_top=bool(capture or capture_dir),
        js_api=DialogAPI(DEFAULT_QUALIFICATION_ROOT, EXPORT_ROOT),
    )
    assert window is not None
    window.events.closed += lambda: closed.set()

    def after_start() -> None:
        deadline = time.perf_counter() + 8.0
        while time.perf_counter() < deadline and not _window_rect(TITLE):
            time.sleep(0.05)
        result["window"] = bool(_window_rect(TITLE))
        result["window_visible_ms"] = round((time.perf_counter() - started) * 1000, 3)
        time.sleep(2.0)
        if capture_dir:
            capture_dir.mkdir(parents=True, exist_ok=True)
            if scenario == "screens":
                result["captures"] = run_screens(window, capture_dir)
            elif scenario == "interactions":
                result["captures"] = run_interactions(window, capture_dir)
            elif scenario == "resize":
                result["captures"] = run_resize(window, capture_dir)
            elif scenario == "project-cycle":
                captures, checks = run_project_cycle(
                    window, capture_dir, DEFAULT_QUALIFICATION_ROOT
                )
                result["captures"] = captures
                result["project_checks"] = checks
            elif scenario == "web04-cycle":
                captures, checks = run_web04_cycle(window, capture_dir, DEFAULT_QUALIFICATION_ROOT)
                result["captures"] = captures
                result["project_checks"] = checks
            elif scenario == "power-balance-05":
                captures, checks = run_power_balance_05(
                    window, capture_dir, DEFAULT_QUALIFICATION_ROOT
                )
                result["captures"] = captures
                result["project_checks"] = checks
            elif scenario == "reporting-06":
                captures, checks = run_reporting_06(window, capture_dir, DEFAULT_QUALIFICATION_ROOT)
                result["captures"] = captures
                result["report_checks"] = checks
            elif scenario == "native-dialog":
                captures, checks = run_native_dialog(window, capture_dir)
                result["captures"] = captures
                result["dialog_checks"] = checks
        if capture:
            result["capture"] = capture_window(TITLE, capture)
            result["capture_ms"] = round((time.perf_counter() - started) * 1000, 3)
            print(json.dumps({"event": "capture", "path": str(capture), "ok": result["capture"]}))
        if auto_close:
            time.sleep(max(0.0, auto_close - (time.perf_counter() - started)))
            window.destroy()
        else:
            closed.wait(3600)

    webview.start(
        after_start,
        gui="edgechromium",
        debug=False,
        private_mode=True,
        icon=str(ICON) if ICON.is_file() else None,
    )
    result["closed_ms"] = round((time.perf_counter() - started) * 1000, 3)
    print(json.dumps({"event": "native_result", **result}, ensure_ascii=True))
    return 0 if result["window"] else 2


def self_check() -> int:
    handle = ServerHandle()
    try:
        url = handle.start()
        health = handle.request("GET", "/api/health")
        info = handle.request("GET", "/api/engine/info")
        project = handle.request("GET", "/api/engine/project")
        power = handle.request(
            "POST",
            "/api/engine/power",
            json={
                "mode": "P_KNOWN",
                "network": "TRI",
                "voltage_v": "400",
                "power_value": "8000",
                "power_unit": "W",
                "power_factor": "0.8",
                "power_nature": "ABSORBED",
                "efficiency": None,
            },
        )
        project_payload = project.json()
        payload = {
            "url": _redacted_url(url),
            "health_status": health.status_code,
            "health": health.json(),
            "engine_info_status": info.status_code,
            "engine_info": info.json(),
            "project_status": project.status_code,
            "project_counts": {
                key: project_payload.get("project", {}).get(key)
                for key in ("load_count", "board_count", "feeder_count")
            },
            "load_rows": len(project_payload.get("loads", [])),
            "power_status": power.status_code,
            "power": power.json(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return (
            0
            if all(response.status_code == 200 for response in (health, info, project, power))
            else 1
        )
    finally:
        handle.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description="SEGYRCALC WEB-02 native shell")
    parser.add_argument(
        "--self-check", action="store_true", help="vérifie l'API sans ouvrir de fenêtre"
    )
    parser.add_argument("--capture", type=Path, help="capture PNG de la fenêtre native")
    parser.add_argument("--capture-dir", type=Path, help="répertoire des captures de scénario")
    parser.add_argument(
        "--auto-close", type=float, default=0, help="fermeture automatique après N secondes"
    )
    parser.add_argument(
        "--screen",
        choices=(
            "dashboard",
            "projects",
            "architecture",
            "balance",
            "library",
            "reports",
            "settings",
            "engine",
            "performance",
        ),
        default="dashboard",
        help="écran initial du prototype",
    )
    parser.add_argument(
        "--run-engine", action="store_true", help="lance automatiquement le calcul B3-01"
    )
    parser.add_argument(
        "--run-error", action="store_true", help="lance automatiquement une entrée invalide"
    )
    parser.add_argument(
        "--scenario",
        choices=(
            "screens",
            "interactions",
            "resize",
            "project-cycle",
            "web04-cycle",
            "power-balance-05",
            "reporting-06",
            "native-dialog",
        ),
        help="scénario de qualification",
    )
    args = parser.parse_args()

    if args.self_check:
        return self_check()

    handle = ServerHandle()
    try:
        url = handle.start()
        params: list[str] = []
        if args.screen != "dashboard":
            params.append(f"screen={args.screen}")
        if args.run_engine:
            params.append("run=1")
        if args.run_error:
            params.append("run=error")
        if params:
            url = f"{url}?{'&'.join(params)}"
        print(json.dumps({"event": "server_started", "url": _redacted_url(url)}))
        return run_native(
            url,
            capture=args.capture,
            capture_dir=args.capture_dir,
            auto_close=args.auto_close if args.auto_close > 0 else None,
            scenario=args.scenario,
        )
    finally:
        handle.stop()


if __name__ == "__main__":
    raise SystemExit(main())
