import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  closeProject,
  createProject,
  duplicateProject,
  listClients,
  listProjectFiles,
  openProject,
  saveProject,
  saveProjectAs,
  updateGeneralInfo,
} from "../api";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { PathDialog } from "../components/PathDialog";
import { ProjectFormDialog } from "../components/ProjectFormDialog";
import { StatusIndicator } from "../components/StatusIndicator";
import { chooseOpenFile, chooseSaveFile, hasNativeFileDialog } from "../desktop";
import { shortDate } from "../format";
import { Icon } from "../icons";
import type { Client, ProjectFile, ProjectPayload, Screen } from "../types";

function errorText(error: unknown): string {
  return error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Opération impossible.";
}

function bytes(value: number): string {
  return value > 1024 * 1024 ? `${(value / 1024 / 1024).toFixed(1)} Mo` : `${Math.ceil(value / 1024)} Ko`;
}

export function ProjectsScreen({
  project,
  onProjectChanged,
  onNavigate,
  onToast,
}: {
  project: ProjectPayload | null;
  onProjectChanged: (project: ProjectPayload | null) => void;
  onNavigate: (screen: Screen) => void;
  onToast: (message: string, tone: "info" | "success" | "warning" | "error") => void;
}) {
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [filesRoot, setFilesRoot] = useState("Répertoire utilisateur");
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [pathMode, setPathMode] = useState<"open" | "save" | "duplicate" | null>(null);
  const [confirmClose, setConfirmClose] = useState(false);
  const [pendingOpen, setPendingOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [pathError, setPathError] = useState<string | null>(null);

  const refreshFiles = () => {
    listProjectFiles()
      .then((result) => {
        setFiles(result.files);
        setFilesRoot(result.root);
      })
      .catch(() => setFiles([]));
  };
  useEffect(refreshFiles, [project?.state.file_path]);

  const refreshClients = () => {
    listClients()
      .then((result) => setClients(result.clients))
      .catch(() => setClients([]));
  };
  useEffect(refreshClients, []);

  const defaultSaveName = useMemo(() => {
    const base = project?.project.reference?.replace(/[^A-Za-z0-9._-]+/g, "-") || "SEGYRCALC-projet";
    return `${base}.segyrcalc-web.json`;
  }, [project?.project.reference]);

  const duplicatePath = useMemo(() => {
    if (project?.state.file_path) {
      return project.state.file_path.replace(/\.segyrcalc-web\.json$/i, "-copie.segyrcalc-web.json");
    }
    return defaultSaveName.replace(/\.segyrcalc-web\.json$/i, "-copie.segyrcalc-web.json");
  }, [defaultSaveName, project?.state.file_path]);

  const run = async <T,>(operation: () => Promise<T>, success: () => void) => {
    setBusy(true);
    setError(null);
    setFormError(null);
    setPathError(null);
    try {
      await operation();
      success();
      refreshFiles();
    } catch (caught) {
      const message = errorText(caught);
      setError(message);
      setFormError(message);
      setPathError(message);
      onToast(message, "error");
    } finally {
      setBusy(false);
    }
  };

  const handleCreate = (payload: Record<string, unknown>) => {
    void run(
      async () => {
        const created = await createProject(payload);
        onProjectChanged(created);
        setCreateOpen(false);
        onToast("Projet créé en mémoire. Il n'est pas encore enregistré.", "info");
        onNavigate("architecture");
      },
      () => undefined,
    );
  };

  const handleGeneral = (payload: Record<string, unknown>) => {
    void run(
      async () => {
        const updated = await updateGeneralInfo(payload, project?.state.revision ?? 1);
        onProjectChanged(updated);
        setEditOpen(false);
        onToast("Informations générales mises à jour. Pensez à enregistrer.", "info");
      },
      () => undefined,
    );
  };

  const doOpenPath = (path: string) => {
    void run(
      async () => {
        const opened = await openProject(path);
        onProjectChanged(opened);
        setPathMode(null);
        setPendingOpen(null);
        onToast("Projet ouvert.", "success");
        onNavigate("balance");
      },
      () => undefined,
    );
  };

  const handleOpenPath = (path: string) => {
    if (project?.state.dirty) {
      setPendingOpen(path);
      return;
    }
    doOpenPath(path);
  };

  const openWithDialog = async () => {
    if (hasNativeFileDialog()) {
      const path = await chooseOpenFile();
      if (path) handleOpenPath(path);
      return;
    }
    setPathMode("open");
  };

  const saveAsWithDialog = async () => {
    if (hasNativeFileDialog()) {
      const path = await chooseSaveFile(defaultSaveName);
      if (path) {
        void run(
          async () => {
            const saved = await saveProjectAs(path, false);
            onProjectChanged(saved);
            onToast("Projet enregistré sous un nouveau nom.", "success");
          },
          () => undefined,
        );
      }
      return;
    }
    setPathMode("save");
  };

  const duplicateWithDialog = async () => {
    if (hasNativeFileDialog()) {
      const path = await chooseSaveFile(duplicatePath.split(/[\\/]/).pop() ?? "projet-copie.segyrcalc-web.json");
      if (path) {
        void run(
          async () => {
            const copied = await duplicateProject(path, false);
            onProjectChanged(copied);
            onToast("Projet dupliqué avec un nouvel identifiant.", "success");
          },
          () => undefined,
        );
      }
      return;
    }
    setPathMode("duplicate");
  };

  const handleSave = () => {
    if (!project) return;
    if (project.state.read_only_source || !project.state.file_path) {
      void saveAsWithDialog();
      return;
    }
    void run(
      async () => {
        const saved = await saveProject(null, true);
        onProjectChanged(saved);
        onToast("Projet enregistré.", "success");
      },
      () => undefined,
    );
  };

  const handleClose = () => {
    if (!project) return;
    if (project.state.dirty) {
      setConfirmClose(true);
      return;
    }
    void doClose();
  };

  const doClose = () => {
    void run(
      async () => {
        await closeProject();
        onProjectChanged(null);
        setConfirmClose(false);
        onToast("Projet fermé.", "info");
      },
      () => undefined,
    );
  };

  const stateLabel = !project
    ? "Aucun projet"
    : project.state.read_only_source
      ? "Lecture seule"
      : project.state.last_error
        ? "Erreur de calcul"
        : project.state.dirty
          ? "Non enregistré"
          : "Enregistré";

  return (
    <div className="page-stack" data-testid="projects-screen">
      <PageHeader
        eyebrow="Projets · gestion locale"
        title="Créez, ouvrez et enregistrez vos projets."
        description="Les projets WEB-07 sont stockés dans le répertoire utilisateur SEGYRCALC. Les fichiers V1.3/V1.4 restent en lecture seule."
        badge={<span className="outline-badge">{hasNativeFileDialog() ? "Dialogues Windows" : "Chemins contrôlés"}</span>}
        actions={
          <>
            <button type="button" className="button button-secondary" onClick={() => setCreateOpen(true)} data-testid="project-new">
              <Icon name="projects" size={16} /> Nouveau projet
            </button>
            <button type="button" className="button button-secondary" onClick={() => void openWithDialog()} data-testid="project-open">
              <Icon name="file" size={16} /> Ouvrir
            </button>
          </>
        }
      />

      {error && <div className="inline-alert inline-alert-error"><Icon name="alert" size={16} /> <span>{error}</span></div>}

      {!project ? (
        <div className="panel">
          <EmptyState
            icon="projects"
            title="Aucun projet ouvert"
            description="Créez un projet vide ou ouvrez un fichier de qualification. Aucun fichier n'est écrit avant une action explicite d'enregistrement."
            action={<button type="button" className="button button-primary" onClick={() => setCreateOpen(true)}>Créer un projet</button>}
          />
        </div>
      ) : (
        <section className="panel project-current">
          <div className="panel-head">
            <div>
              <span className="eyebrow">Projet actif</span>
              <h2>{project.project.name}</h2>
              <span className="mono">{project.project.reference}</span>
            </div>
            <div className="project-state-badges">
              <span className={`badge ${project.state.read_only_source ? "badge-neutral" : project.state.dirty ? "badge-warn" : "badge-ok"}`}>{stateLabel}</span>
              <StatusIndicator status={project.status} compact />
            </div>
          </div>
          <div className="project-summary">
            <div><span>Client</span><strong>{project.project.client || "—"}</strong></div>
            <div><span>Site</span><strong>{project.web.site || "—"}</strong></div>
            <div><span>Auteur</span><strong>{project.web.created_by || "—"}</strong></div>
            <div><span>Récepteurs</span><strong>{project.project.load_count}</strong></div>
            <div><span>Tableaux</span><strong>{project.project.board_count}</strong></div>
            <div><span>Départs</span><strong>{project.project.feeder_count}</strong></div>
            <div className="wide"><span>Fichier</span><strong className="mono">{project.state.file_path ?? "Non enregistré"}</strong></div>
            <div><span>Révision</span><strong>{project.state.revision}</strong></div>
            <div><span>Format</span><strong>{project.state.source_format}</strong></div>
          </div>
          {project.state.read_only_source && (
            <div className="notice notice-warning"><Icon name="lock" size={15} /><span>Projet historique ouvert en lecture seule. Utilisez « Enregistrer sous » pour créer une copie WEB-07.</span></div>
          )}
          <div className="project-actions">
            <button type="button" className="button button-primary" onClick={handleSave} disabled={busy || !project.state.dirty} data-testid="project-save">
              <Icon name="check" size={15} /> Enregistrer
            </button>
            <button type="button" className="button button-secondary" onClick={() => void saveAsWithDialog()} disabled={busy} data-testid="project-save-as">
              <Icon name="file" size={15} /> Enregistrer sous
            </button>
            <button type="button" className="button button-secondary" onClick={() => setEditOpen(true)} disabled={busy}>
              <Icon name="edit" size={15} /> Informations
            </button>
            <button type="button" className="button button-secondary" onClick={() => void duplicateWithDialog()} disabled={busy} data-testid="project-duplicate">
              <Icon name="file" size={15} /> Dupliquer
            </button>
            <button type="button" className="button button-secondary" onClick={() => onNavigate("architecture")} data-testid="project-architecture">
              <Icon name="tree" size={15} /> Architecture
            </button>
            <button type="button" className="button button-ghost" onClick={handleClose} disabled={busy} data-testid="project-close">
              <Icon name="close" size={15} /> Fermer
            </button>
          </div>
          <p className="form-note">L'enregistrement utilise un fichier temporaire, une sauvegarde <span className="mono">.bak</span> et un remplacement atomique. Aucun écrasement silencieux n'est effectué.</p>
        </section>
      )}

      <section className="panel">
        <div className="panel-head"><div><span className="eyebrow">Fichiers de qualification</span><h2>Projets accessibles</h2></div><span className="mini-badge">{files.length} fichier(s)</span></div>
        <div className="table-wrap">
          <table className="simple-table" aria-label="Fichiers projet">
            <thead><tr><th>Nom</th><th>Format</th><th>Taille</th><th>Modifié</th><th>Accès</th><th /></tr></thead>
            <tbody>
              {files.map((file) => (
                <tr key={file.path}>
                  <td><div className="cell-main mono">{file.name}</div><div className="cell-sub mono">{file.path}</div></td>
                  <td><span className="badge badge-outline">{file.format}</span></td>
                  <td>{bytes(file.size)}</td>
                  <td>{shortDate(file.modified)}</td>
                  <td>{file.writable ? "Lecture / écriture" : "Lecture seule"}</td>
                  <td className="cell-action"><button type="button" className="text-button" onClick={() => handleOpenPath(file.path)} disabled={busy} data-testid={`open-file-${file.name}`}>Ouvrir <Icon name="arrow" size={13} /></button></td>
                </tr>
              ))}
              {files.length === 0 && <tr><td colSpan={6} className="table-empty">Aucun fichier de qualification.</td></tr>}
            </tbody>
          </table>
        </div>
        <div className="panel-foot"><span className="muted-copy">Répertoire autorisé : <span className="mono">{filesRoot}</span></span></div>
      </section>

      <ProjectFormDialog
        open={createOpen}
        mode="create"
        clients={clients}
        busy={busy}
        error={formError}
        onSubmit={handleCreate}
        onClose={() => setCreateOpen(false)}
        onClientsChanged={refreshClients}
      />
      <ProjectFormDialog
        open={editOpen}
        mode="edit"
        project={project}
        clients={clients}
        busy={busy}
        error={formError}
        onSubmit={handleGeneral}
        onClose={() => setEditOpen(false)}
        onClientsChanged={refreshClients}
      />
      <PathDialog
        open={pathMode !== null}
        mode={pathMode ?? "open"}
        initialPath={pathMode === "duplicate" ? duplicatePath : project?.state.file_path ?? ""}
        busy={busy}
        error={pathError}
        onSubmit={(path, overwrite) => {
          if (pathMode === "open") {
            handleOpenPath(path);
            return;
          }
          void run(async () => {
            if (pathMode === "duplicate") {
              const copied = await duplicateProject(path, overwrite);
              onProjectChanged(copied);
              onToast("Projet dupliqué avec un nouvel identifiant.", "success");
            } else {
              const saved = await saveProjectAs(path, overwrite);
              onProjectChanged(saved);
              onToast("Projet enregistré.", "success");
            }
            setPathMode(null);
          }, () => undefined);
        }}
        onClose={() => setPathMode(null)}
      />
      <ConfirmDialog
        open={confirmClose}
        title="Fermer sans enregistrer ?"
        message="Le projet contient des modifications non enregistrées. Elles seront perdues si vous fermez maintenant."
        confirmLabel="Fermer sans enregistrer"
        danger
        onConfirm={doClose}
        onCancel={() => setConfirmClose(false)}
      />
      <ConfirmDialog
        open={pendingOpen !== null}
        title="Ouvrir un autre projet ?"
        message="Le projet actif contient des modifications non enregistrées. Elles seront perdues si vous ouvrez un autre projet."
        confirmLabel="Ouvrir sans enregistrer"
        danger
        onConfirm={() => pendingOpen && doOpenPath(pendingOpen)}
        onCancel={() => setPendingOpen(null)}
      />
    </div>
  );
}
