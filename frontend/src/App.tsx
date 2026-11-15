import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { loadCurrentProject, redoProject, saveProject, undoProject, updateFeeder, updateLoad } from "./api";
import { AppShell } from "./components/AppShell";
import { ErrorState } from "./components/ErrorState";
import { LoadingState } from "./components/LoadingState";
import { Sidebar } from "./components/Sidebar";
import { Toast } from "./components/Toast";
import { Topbar } from "./components/Topbar";
import { AboutScreen } from "./screens/AboutScreen";
import { ArchitectureScreen } from "./screens/ArchitectureScreen";
import { ClientsScreen } from "./screens/ClientsScreen";
import { DashboardScreen } from "./screens/DashboardScreen";
import { EngineScreen } from "./screens/EngineScreen";
import { LibraryScreen } from "./screens/LibraryScreen";
import { PerformanceScreen } from "./screens/PerformanceScreen";
import { PowerBalanceScreen } from "./screens/PowerBalanceScreen";
import { ProjectsScreen } from "./screens/ProjectsScreen";
import { ReportsScreen } from "./screens/ReportsScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import type { ProjectPayload, Screen, Selection } from "./types";

const allowedScreens: Screen[] = [
  "dashboard", "projects", "clients", "architecture", "balance", "library",
  "reports", "settings", "about", "engine", "performance",
];

const labels: Record<Screen, string> = {
  dashboard: "Accueil",
  projects: "Projets",
  clients: "Clients",
  architecture: "Architecture électrique",
  balance: "Bilan de puissance",
  library: "Bibliothèque",
  reports: "Rapports",
  settings: "Paramètres",
  about: "À propos",
  engine: "Qualification moteur",
  performance: "Performance UI",
};

function initialScreen(): Screen {
  const value = new URLSearchParams(window.location.search).get("screen");
  return allowedScreens.includes(value as Screen) ? (value as Screen) : "dashboard";
}

function rootSelection(project: ProjectPayload): Selection {
  const root = project.boards.find((board) => board.type === "TGBT") ?? project.boards[0];
  return root ? { kind: "board", id: root.id } : { kind: "project", id: "project" };
}

function App() {
  const [screen, setScreen] = useState<Screen>(initialScreen);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [project, setProject] = useState<ProjectPayload | null>(null);
  const [previousProject, setPreviousProject] = useState<ProjectPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [toast, setToast] = useState<{ message: string; tone: "info" | "success" | "warning" | "error" } | null>(null);
  const projectRef = useRef<ProjectPayload | null>(null);

  const showToast = useCallback((message: string, tone: "info" | "success" | "warning" | "error") => {
    setToast({ message, tone });
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    loadCurrentProject()
      .then((payload) => {
        projectRef.current = payload;
        setProject(payload);
        setSelection(payload ? rootSelection(payload) : null);
      })
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Chargement impossible."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);

  const navigate = (next: Screen) => {
    setScreen(next);
    const url = new URL(window.location.href);
    url.searchParams.set("screen", next);
    window.history.replaceState(null, "", url);
  };

  const handleProjectChanged = useCallback((next: ProjectPayload | null) => {
    const current = projectRef.current;
    if (
      next
      && current
      && next.project.id === current.project.id
      && next.state.revision < current.state.revision
    ) {
      return;
    }
    setPreviousProject((previous) => {
      if (!current || !next) return null;
      if (next.project.id !== current.project.id) return null;
      if (next.state.revision > current.state.revision) return current;
      if (next.state.revision === current.state.revision) return previous;
      return null;
    });
    projectRef.current = next;
    setProject(next);
    if (next) {
      setSelection((current) => {
        const exists = next.boards.some((board) => current?.kind === "board" && board.id === current.id)
          || next.feeders.some((feeder) => current?.kind === "feeder" && feeder.id === current.id)
          || next.loads.some((load) => current?.kind === "load" && load.id === current.id);
        return exists ? current : rootSelection(next);
      });
    } else {
      setSelection(null);
      setScreen("projects");
    }
  }, []);

  const historyAction = useCallback(async (action: "undo" | "redo") => {
    const current = projectRef.current;
    if (!current || historyBusy) return;
    setHistoryBusy(true);
    try {
      const next = action === "undo"
        ? await undoProject(current.state.revision)
        : await redoProject(current.state.revision);
      handleProjectChanged(next);
      const label = action === "undo" ? current.state.undo_label : current.state.redo_label;
      showToast(`${action === "undo" ? "Annulation" : "Rétablissement"}${label ? ` : ${label}` : ""}.`, "success");
    } catch (caught) {
      showToast(caught instanceof Error ? caught.message : "Opération d'historique impossible.", "error");
    } finally {
      setHistoryBusy(false);
    }
  }, [handleProjectChanged, historyBusy, showToast]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      const key = event.key.toLowerCase();
      if (key === "z") {
        event.preventDefault();
        void historyAction(event.shiftKey ? "redo" : "undo");
      } else if (key === "y") {
        event.preventDefault();
        void historyAction("redo");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [historyAction]);

  const quickSave = async () => {
    if (!project) return;
    if (!project.state.file_path || project.state.read_only_source) {
      navigate("projects");
      showToast("Choisissez « Enregistrer sous » pour nommer le nouveau fichier.", "info");
      return;
    }
    setSaving(true);
    setSaveError(false);
    try {
      const saved = await saveProject(null, true);
      handleProjectChanged(saved);
      showToast("Projet enregistré.", "success");
    } catch (caught) {
      setSaveError(true);
      showToast(caught instanceof Error ? caught.message : "Enregistrement impossible.", "error");
    } finally {
      setSaving(false);
    }
  };

  const editDesignation = async (id: string, value: string) => {
    const loadItem = project?.loads.find((item) => item.id === id);
    const clean = value.trim();
    if (!project || !loadItem || !clean || clean === loadItem.designation) return;
    try {
      const updated = await updateLoad(id, {
        feeder_id: loadItem.feeder_id,
        designation: clean,
        network: loadItem.network,
        voltage_v: loadItem.voltage_v,
        nominal_power: loadItem.nominal_power,
        power_unit: loadItem.power_unit,
        quantity: loadItem.quantity,
        power_factor: loadItem.power_factor ?? "0.9",
        ku: loadItem.ku,
        phase: loadItem.phase,
      }, project.state.revision);
      handleProjectChanged(updated);
      showToast("Désignation modifiée. Enregistrez pour la conserver.", "warning");
    } catch (caught) {
      showToast(caught instanceof Error ? caught.message : "Modification impossible.", "error");
    }
  };

  const editCoefficient = async (kind: "load" | "feeder", id: string, value: string) => {
    const current = projectRef.current;
    if (!current) return;
    const clean = value.trim().replace(",", ".");
    if (!/^\d+(?:\.\d+)?$/.test(clean)) {
      showToast("Le coefficient doit être une valeur numérique positive.", "error");
      return;
    }
    try {
      let updated: ProjectPayload;
      if (kind === "load") {
        const item = current.loads.find((load) => load.id === id);
        if (!item) return;
        updated = await updateLoad(id, {
          feeder_id: item.feeder_id,
          designation: item.designation,
          network: item.network,
          voltage_v: item.voltage_v,
          nominal_power: item.nominal_power,
          power_unit: item.power_unit,
          quantity: item.quantity,
          power_factor: item.power_factor ?? "0.9",
          ku: clean,
          phase: item.phase,
        }, current.state.revision);
      } else {
        const item = current.feeders.find((feeder) => feeder.id === id);
        if (!item) return;
        updated = await updateFeeder(id, {
          designation: item.designation,
          description: item.description,
          ks: clean,
          phase: item.phase,
          has_neutral: item.has_neutral,
          voltage_ln_v: item.voltage_ln_v,
        }, current.state.revision);
      }
      handleProjectChanged(updated);
      showToast(`${kind === "load" ? "Ku" : "Ks"} modifié et bilan recalculé.`, "success");
    } catch (caught) {
      showToast(caught instanceof Error ? caught.message : "Modification du coefficient impossible.", "error");
    }
  };

  const breadcrumb = useMemo(() => ["SEGYRCALC", labels[screen]], [screen]);
  const topbar = (
    <Topbar
      breadcrumb={breadcrumb}
      projectName={project?.project.name ?? "Aucun projet"}
      projectReference={project?.project.reference ?? ""}
      engineVersion={project?.engine.version ?? "—"}
      dirty={Boolean(project?.state.dirty)}
      readOnly={Boolean(project?.state.read_only_source)}
      saving={saving}
      saveError={saveError}
      theme={theme}
      onToggleTheme={() => setTheme((value) => value === "light" ? "dark" : "light")}
      onSave={() => void quickSave()}
    />
  );

  if (loading) {
    return (
      <AppShell sidebar={<Sidebar screen={screen} onNavigate={navigate} projectName="Chargement…" modified={false} />} topbar={topbar}>
        <LoadingState label="Chargement du projet et du moteur Python…" />
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell sidebar={<Sidebar screen={screen} onNavigate={navigate} projectName="Projet indisponible" modified={false} />} topbar={topbar}>
        <ErrorState title="Le service projet n'a pas répondu" message={error} onRetry={load} />
      </AppShell>
    );
  }

  if (!project) {
    const noProjectContent = screen === "settings"
      ? <SettingsScreen project={null} theme={theme} onToggleTheme={() => setTheme((value) => value === "light" ? "dark" : "light")} onNavigate={navigate} modifiedCount={0} onReset={() => undefined} />
      : screen === "about"
        ? <AboutScreen engineVersion="1.3.0" engineFacade="calcelect.service_v13.calculate_project_v13" />
        : screen === "clients"
        ? <ClientsScreen onToast={showToast} />
        : screen === "engine"
          ? <EngineScreen />
          : <ProjectsScreen project={null} onProjectChanged={handleProjectChanged} onNavigate={navigate} onToast={showToast} />;
    return (
      <AppShell sidebar={<Sidebar screen={screen} onNavigate={navigate} projectName="Aucun projet" modified={false} />} topbar={topbar}>
        {noProjectContent}
      </AppShell>
    );
  }

  return (
    <>
      <AppShell
        sidebar={<Sidebar screen={screen} onNavigate={navigate} projectName={project.project.name} modified={Boolean(project.state.dirty)} />}
        topbar={topbar}
      >
        {screen === "dashboard" && <DashboardScreen project={project} loading={false} error={null} onNavigate={navigate} />}
        {screen === "projects" && <ProjectsScreen project={project} onProjectChanged={handleProjectChanged} onNavigate={navigate} onToast={showToast} />}
        {screen === "clients" && <ClientsScreen onToast={showToast} />}
        {screen === "architecture" && (
          <ArchitectureScreen
            project={project}
            selection={selection}
            onSelect={setSelection}
            temporaryEdits={{}}
            onEditDesignation={(id, value) => void editDesignation(id, value)}
            onReset={() => navigate("projects")}
            onProjectChanged={handleProjectChanged}
            onToast={showToast}
            onUndo={() => void historyAction("undo")}
            onRedo={() => void historyAction("redo")}
            historyBusy={historyBusy}
          />
        )}
        {screen === "balance" && (
          <PowerBalanceScreen
            project={project}
            previousProject={previousProject}
            selection={selection}
            onSelect={setSelection}
            temporaryEdits={{}}
            onEditDesignation={(id, value) => void editDesignation(id, value)}
            onEditCoefficient={(kind, id, value) => void editCoefficient(kind, id, value)}
            onReset={() => navigate("projects")}
          />
        )}
        {screen === "library" && <LibraryScreen />}
        {screen === "reports" && <ReportsScreen project={project} onNotify={showToast} />}
        {screen === "settings" && (
          <SettingsScreen
            project={project}
            theme={theme}
            onToggleTheme={() => setTheme((value) => value === "light" ? "dark" : "light")}
            onNavigate={navigate}
            modifiedCount={project.state.dirty ? 1 : 0}
            onReset={() => navigate("projects")}
          />
        )}
        {screen === "about" && (
          <AboutScreen
            engineVersion={project.engine.version}
            engineFacade={project.engine.facade}
          />
        )}
        {screen === "engine" && <EngineScreen />}
        {screen === "performance" && <PerformanceScreen project={project} />}
      </AppShell>
      {toast && <Toast message={toast.message} tone={toast.tone} onClose={() => setToast(null)} />}
    </>
  );
}

export default App;



