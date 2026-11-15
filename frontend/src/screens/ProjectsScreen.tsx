import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError,
  closeProject,
  createProject,
  duplicateProject,
  listClients,
  listProjectCatalog,
  openCatalogProject,
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
import type {
  Client,
  ProjectCatalogItem,
  ProjectCatalogQuery,
  ProjectCatalogResponse,
  ProjectPayload,
  ProjectProgress,
  Screen,
} from "../types";

type CatalogSort = NonNullable<ProjectCatalogQuery["sort"]>;
type PageSize = NonNullable<ProjectCatalogQuery["page_size"]>;

const PROGRESS_LABELS: Record<ProjectProgress, string> = {
  NOT_DEFINED: "Non défini",
  IN_PROGRESS: "En cours",
  COMPLETED: "Terminé",
};

const SORT_LABELS: Record<CatalogSort, string> = {
  name_asc: "Nom A → Z",
  name_desc: "Nom Z → A",
  updated_desc: "Modifié récemment",
  updated_asc: "Modifié anciennement",
  created_desc: "Créé récemment",
  created_asc: "Créé anciennement",
  client_asc: "Client A → Z",
  client_desc: "Client Z → A",
};

function errorText(error: unknown): string {
  return error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Opération impossible.";
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
  const [catalog, setCatalog] = useState<ProjectCatalogResponse | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [pathMode, setPathMode] = useState<"open" | "save" | "duplicate" | null>(null);
  const [confirmClose, setConfirmClose] = useState(false);
  const [pendingOpen, setPendingOpen] = useState<string | null>(null);
  const [pendingCatalogId, setPendingCatalogId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [pathError, setPathError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [clientFilter, setClientFilter] = useState("");
  const [progressFilter, setProgressFilter] = useState<ProjectProgress | "">("");
  const [dateField, setDateField] = useState<"created" | "updated">("updated");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sort, setSort] = useState<CatalogSort>("updated_desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<PageSize>(25);
  const catalogRequest = useRef(0);

  const refreshCatalog = useCallback(() => {
    const requestId = ++catalogRequest.current;
    setCatalogLoading(true);
    setCatalogError(null);
    listProjectCatalog({
      q: query,
      client_id: clientFilter || null,
      progress: progressFilter || null,
      date_field: dateField,
      date_from: dateFrom,
      date_to: dateTo,
      sort,
      page,
      page_size: pageSize,
    })
      .then((result) => {
        if (requestId === catalogRequest.current) {
          setCatalog(result);
        }
      })
      .catch((caught) => {
        if (requestId === catalogRequest.current) {
          setCatalog(null);
          setCatalogError(errorText(caught));
        }
      })
      .finally(() => {
        if (requestId === catalogRequest.current) {
          setCatalogLoading(false);
        }
      });
  }, [clientFilter, dateField, dateFrom, dateTo, page, pageSize, progressFilter, query, sort]);

  useEffect(() => {
    refreshCatalog();
  }, [refreshCatalog]);

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
      refreshCatalog();
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
        setPendingCatalogId(null);
        onToast("Projet ouvert.", "success");
        onNavigate("balance");
      },
      () => undefined,
    );
  };

  const doOpenCatalog = (catalogId: string) => {
    void run(
      async () => {
        const opened = await openCatalogProject(catalogId);
        onProjectChanged(opened);
        setPendingOpen(null);
        setPendingCatalogId(null);
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

  const handleOpenCatalog = (item: ProjectCatalogItem) => {
    if (project?.state.dirty) {
      setPendingCatalogId(item.catalog_id);
      return;
    }
    doOpenCatalog(item.catalog_id);
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

  const resetFilters = () => {
    setQuery("");
    setClientFilter("");
    setProgressFilter("");
    setDateField("updated");
    setDateFrom("");
    setDateTo("");
    setSort("updated_desc");
    setPage(1);
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

  const items = catalog?.items ?? [];
  const total = catalog?.total ?? 0;
  const pageCount = catalog?.total_pages ?? 0;
  const currentPage = catalog?.page ?? page;

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
        <div className="panel-head">
          <div><span className="eyebrow">Catalogue local</span><h2>Projets accessibles</h2></div>
          <span className="mini-badge">{catalogLoading ? "Chargement…" : `${total} projet(s)`}</span>
        </div>

        <div className="toolbar toolbar-inside">
          <div className="toolbar-left">
            <label className="search-input">
              <Icon name="search" size={14} />
              <input
                type="search"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setPage(1);
                }}
                placeholder="Nom, référence, client, description"
                aria-label="Rechercher un projet"
                data-testid="project-search"
              />
              {query && (
                <button type="button" className="search-clear" aria-label="Effacer la recherche" onClick={() => { setQuery(""); setPage(1); }}>
                  <Icon name="close" size={12} />
                </button>
              )}
            </label>
            <label className="select-control">
              <Icon name="filter" size={13} />
              <span>Client</span>
              <select value={clientFilter} onChange={(event) => { setClientFilter(event.target.value); setPage(1); }} aria-label="Filtrer par client" data-testid="project-client-filter">
                <option value="">Tous</option>
                {clients.map((client) => (
                  <option key={client.id} value={client.id}>
                    {client.company_name}{client.is_archived ? " (archivé)" : ""}
                  </option>
                ))}
              </select>
            </label>
            <label className="select-control">
              <span>Progression</span>
              <select value={progressFilter} onChange={(event) => { setProgressFilter(event.target.value as ProjectProgress | ""); setPage(1); }} aria-label="Filtrer par progression" data-testid="project-progress-filter">
                <option value="">Toutes</option>
                <option value="NOT_DEFINED">Non défini</option>
                <option value="IN_PROGRESS">En cours</option>
                <option value="COMPLETED">Terminé</option>
              </select>
            </label>
            <label className="select-control">
              <span>Date</span>
              <select value={dateField} onChange={(event) => { setDateField(event.target.value as "created" | "updated"); setPage(1); }} aria-label="Champ de date filtré" data-testid="project-date-field">
                <option value="updated">Modification</option>
                <option value="created">Création</option>
              </select>
            </label>
            <input type="date" value={dateFrom} onChange={(event) => { setDateFrom(event.target.value); setPage(1); }} aria-label="Date de début" data-testid="project-date-from" />
            <input type="date" value={dateTo} onChange={(event) => { setDateTo(event.target.value); setPage(1); }} aria-label="Date de fin" data-testid="project-date-to" />
          </div>
          <div className="toolbar-right">
            <label className="select-control">
              <span>Trier</span>
              <select value={sort} onChange={(event) => { setSort(event.target.value as CatalogSort); setPage(1); }} aria-label="Trier les projets" data-testid="project-sort">
                {Object.entries(SORT_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label className="select-control">
              <span>Par page</span>
              <select value={String(pageSize)} onChange={(event) => { setPageSize(Number(event.target.value) as PageSize); setPage(1); }} aria-label="Nombre de projets par page" data-testid="project-page-size">
                <option value="25">25</option>
                <option value="50">50</option>
                <option value="100">100</option>
              </select>
            </label>
            <button type="button" className="button button-ghost button-small" onClick={resetFilters} data-testid="project-reset-filters">Réinitialiser</button>
          </div>
        </div>

        {catalogError && <div className="inline-alert inline-alert-error"><Icon name="alert" size={15} /><span>{catalogError}</span></div>}

        <div className="table-wrap">
          <table className="simple-table" aria-label="Catalogue des projets">
            <thead>
              <tr>
                <th>Projet</th>
                <th>Client</th>
                <th>Progression</th>
                <th>Modifié</th>
                <th>Format</th>
                <th><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.catalog_id}>
                  <td>
                    <div className="cell-main">{item.name}</div>
                    <div className="cell-sub">
                      {item.reference || "Sans référence"}{item.description ? ` · ${item.description}` : ""}
                    </div>
                    {item.metadata_error && <div className="cell-sub">Métadonnées incomplètes</div>}
                  </td>
                  <td>{item.client_name || "—"}</td>
                  <td><span className="badge badge-outline">{PROGRESS_LABELS[item.progress]}</span></td>
                  <td>{item.updated_at ? shortDate(item.updated_at) : item.file_modified ? shortDate(item.file_modified) : "—"}</td>
                  <td><span className="badge badge-outline">{item.format}</span></td>
                  <td className="cell-action">
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => handleOpenCatalog(item)}
                      disabled={busy}
                      data-testid={`open-project-${item.catalog_id}`}
                    >
                      Ouvrir <Icon name="arrow" size={13} />
                    </button>
                  </td>
                </tr>
              ))}
              {catalogLoading && items.length === 0 && <tr><td colSpan={6} className="table-empty">Chargement du catalogue…</td></tr>}
              {!catalogLoading && items.length === 0 && (
                <tr><td colSpan={6} className="table-empty">{catalogError ? "Catalogue indisponible." : "Aucun projet ne correspond aux critères."}</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="panel-foot">
          <span>{catalogLoading ? "Recherche en cours…" : `${total} résultat(s) · page ${currentPage} / ${Math.max(pageCount, 1)}`}</span>
          <div className="toolbar-right">
            <button type="button" className="button button-secondary button-small" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={catalogLoading || !catalog?.has_previous} data-testid="project-page-previous">Précédent</button>
            <button type="button" className="button button-secondary button-small" onClick={() => setPage((value) => value + 1)} disabled={catalogLoading || !catalog?.has_next} data-testid="project-page-next">Suivant</button>
          </div>
        </div>
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
      <ConfirmDialog
        open={pendingCatalogId !== null}
        title="Ouvrir un autre projet ?"
        message="Le projet actif contient des modifications non enregistrées. Elles seront perdues si vous ouvrez un autre projet."
        confirmLabel="Ouvrir sans enregistrer"
        danger
        onConfirm={() => pendingCatalogId && doOpenCatalog(pendingCatalogId)}
        onCancel={() => setPendingCatalogId(null)}
      />
    </div>
  );
}
