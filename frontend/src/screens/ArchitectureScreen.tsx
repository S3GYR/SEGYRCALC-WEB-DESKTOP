import { useMemo, useState } from "react";
import {
  addBoard,
  addFeeder,
  addFeederWithLoad,
  addLoad,
  deleteBoard,
  deleteFeeder,
  deleteLoad,
  deletionPreview,
  duplicateBoard,
  duplicateFeeder,
  duplicateLoad,
  moveBoard,
  moveFeeder,
  moveLoad,
  recalculateProject,
  updateBoard,
  updateFeeder,
  updateLoad,
} from "../api";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { ElectricalGraphView } from "../components/ElectricalGraphView";
import { EntityDialog } from "../components/EntityDialog";
import { FeederLoadDialog } from "../components/FeederLoadDialog";
import { MoveDuplicateDialog } from "../components/MoveDuplicateDialog";
import { PageHeader } from "../components/PageHeader";
import { SourcePanel } from "../components/SourcePanel";
import { SearchInput } from "../components/SearchInput";
import { SummaryCard } from "../components/SummaryCard";
import { Tabs } from "../components/Tabs";
import { Toolbar } from "../components/Toolbar";
import { TreeView } from "../components/TreeView";
import { allowedDistributionTypes } from "../data/distribution";
import { buildElectricalTree, loadById } from "../data/hierarchy";
import { Icon } from "../icons";
import type {
  BoardSummary,
  DeletionPreview,
  FeederSummary,
  LoadSummary,
  ProjectPayload,
  Selection,
  TemporaryEdits,
} from "../types";
import { PropertyContent } from "./PropertyContent";

type EntityKind = "board" | "feeder" | "load";
type DialogState = { kind: EntityKind; mode: "create" | "edit" } | null;
type ActionState = { action: "move" | "duplicate"; kind: EntityKind } | null;
type DeleteTarget = {
  kind: EntityKind;
  id: string;
  label: string;
  preview: DeletionPreview;
} | null;

export function ArchitectureScreen({
  project,
  selection,
  onSelect,
  temporaryEdits,
  onEditDesignation,
  onReset,
  onProjectChanged,
  onToast,
  onUndo,
  onRedo,
  historyBusy,
}: {
  project: ProjectPayload;
  selection: Selection | null;
  onSelect: (selection: Selection) => void;
  temporaryEdits: TemporaryEdits;
  onEditDesignation: (id: string, value: string) => void;
  onReset: () => void;
  onProjectChanged: (project: ProjectPayload) => void;
  onToast: (message: string, tone: "info" | "success" | "warning" | "error") => void;
  onUndo: () => void;
  onRedo: () => void;
  historyBusy: boolean;
}) {
  const [search, setSearch] = useState("");
  const [view, setView] = useState<"tree" | "graph">("tree");
  const [dialog, setDialog] = useState<DialogState>(null);
  const [feederLoadOpen, setFeederLoadOpen] = useState(false);
  const [actionDialog, setActionDialog] = useState<ActionState>(null);
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const tree = useMemo(
    () => buildElectricalTree(project, project.unassigned_loads ?? []),
    [project],
  );

  const selectedBoard = selection?.kind === "board" ? project.boards.find((board) => board.id === selection.id) ?? null : null;
  const selectedFeeder = selection?.kind === "feeder" ? project.feeders.find((feeder) => feeder.id === selection.id) ?? null : null;
  const selectedLoad = selection?.kind === "load" ? loadById(project, selection.id) : null;
  const initial: BoardSummary | FeederSummary | LoadSummary | null = selectedBoard ?? selectedFeeder ?? selectedLoad;
  const selectedKind: EntityKind | null = selection?.kind === "board" || selection?.kind === "feeder" || selection?.kind === "load"
    ? selection.kind
    : null;

  const run = async (
    operation: () => Promise<ProjectPayload>,
    success: string,
    after?: (updated: ProjectPayload) => void,
  ) => {
    setBusy(true);
    setError(null);
    try {
      const updated = await operation();
      onProjectChanged(updated);
      after?.(updated);
      onToast(success, "success");
      setDialog(null);
      setActionDialog(null);
      setDeleteTarget(null);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Opération impossible.";
      setError(message);
      onToast(message, "error");
    } finally {
      setBusy(false);
    }
  };

  const submitEntity = (payload: Record<string, unknown>) => {
    if (!dialog) return;
    const revision = project.state.revision;
    if (dialog.kind === "board") {
      void run(
        () => dialog.mode === "create"
          ? addBoard(payload, revision)
          : updateBoard(selectedBoard?.id ?? "", payload, revision),
        dialog.mode === "create" ? "Tableau ajouté." : "Tableau modifié.",
      );
    } else if (dialog.kind === "feeder") {
      void run(
        () => dialog.mode === "create"
          ? addFeeder(payload, revision)
          : updateFeeder(selectedFeeder?.id ?? "", payload, revision),
        dialog.mode === "create" ? "Départ ajouté." : "Départ modifié.",
      );
    } else {
      void run(
        () => dialog.mode === "create"
          ? addLoad(payload, revision)
          : updateLoad(selectedLoad?.id ?? "", payload, revision),
        dialog.mode === "create" ? "Récepteur ajouté et bilan recalculé." : "Récepteur modifié et bilan recalculé.",
      );
    }
  };

  const canCreatePair = Boolean(selectedBoard && allowedDistributionTypes(selectedBoard).length > 0);

  const submitFeederLoad = (payload: Record<string, unknown>) => {
    if (!selectedBoard) return;
    const revision = project.state.revision;
    const oldFeederIds = new Set(project.feeders.map((feeder) => feeder.id));
    void run(
      () => addFeederWithLoad(payload, revision),
      "Départ et premier récepteur créés, bilan recalculé.",
      (updated) => {
        setFeederLoadOpen(false);
        const created = updated.feeders.find((feeder) => !oldFeederIds.has(feeder.id));
        if (created) onSelect({ kind: "feeder", id: created.id });
      },
    );
  };

  const openDelete = async () => {
    if (!selectedKind) return;
    const entity = selectedKind === "board" ? selectedBoard : selectedKind === "feeder" ? selectedFeeder : selectedLoad;
    if (!entity) return;
    setError(null);
    try {
      const preview = await deletionPreview(selectedKind, entity.id);
      if (preview.root) {
        onToast("Le TGBT racine ne peut pas être supprimé.", "error");
        return;
      }
      setDeleteTarget({ kind: selectedKind, id: entity.id, label: entity.designation, preview });
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Aperçu de suppression impossible.";
      setError(message);
      onToast(message, "error");
    }
  };

  const confirmDelete = () => {
    if (!deleteTarget) return;
    const revision = project.state.revision;
    const operation = deleteTarget.kind === "board"
      ? deleteBoard(deleteTarget.id, revision, true)
      : deleteTarget.kind === "feeder"
        ? deleteFeeder(deleteTarget.id, revision, true)
        : deleteLoad(deleteTarget.id, revision, false);
    void run(() => operation, "Suppression contrôlée appliquée et bilan recalculé.");
  };

  const submitAction = (payload: Record<string, unknown>) => {
    if (!actionDialog || !initial) return;
    const revision = project.state.revision;
    const oldBoardIds = new Set(project.boards.map((board) => board.id));
    const oldFeederIds = new Set(project.feeders.map((feeder) => feeder.id));
    const oldLoadIds = new Set(project.loads.map((load) => load.id));
    const selectNew = (updated: ProjectPayload) => {
      if (actionDialog.kind === "board") {
        const created = updated.boards.find((board) => !oldBoardIds.has(board.id));
        if (created) onSelect({ kind: "board", id: created.id });
      } else if (actionDialog.kind === "feeder") {
        const created = updated.feeders.find((feeder) => !oldFeederIds.has(feeder.id));
        if (created) onSelect({ kind: "feeder", id: created.id });
      } else {
        const created = updated.loads.find((load) => !oldLoadIds.has(load.id));
        if (created) onSelect({ kind: "load", id: created.id });
      }
    };
    if (actionDialog.action === "move") {
      if (actionDialog.kind === "board") {
        void run(
          () => moveBoard(initial.id, String(payload.destination_board_id), revision),
          "Tableau déplacé.",
        );
      } else if (actionDialog.kind === "feeder") {
        void run(
          () => moveFeeder(initial.id, String(payload.destination_board_id), revision),
          "Départ déplacé.",
        );
      } else {
        void run(
          () => moveLoad(initial.id, String(payload.destination_feeder_id), revision),
          "Récepteur réaffecté.",
        );
      }
      return;
    }
    if (actionDialog.kind === "board") {
      void run(
        () => duplicateBoard(initial.id, payload.destination_board_id ? String(payload.destination_board_id) : null, revision),
        "Tableau dupliqué avec de nouveaux identifiants.",
        selectNew,
      );
    } else if (actionDialog.kind === "feeder") {
      void run(
        () => duplicateFeeder(initial.id, payload.destination_board_id ? String(payload.destination_board_id) : null, revision),
        "Départ dupliqué avec ses récepteurs.",
        selectNew,
      );
    } else {
      void run(
        () => duplicateLoad(initial.id, payload.destination_feeder_id ? String(payload.destination_feeder_id) : null, revision),
        "Récepteur dupliqué.",
        selectNew,
      );
    }
  };

  const canMove = Boolean(initial) && !(selectedBoard && selectedBoard.type === "TGBT") && !(selectedFeeder?.downstream_board_id);
  const canDuplicate = Boolean(initial) && !(selectedBoard && selectedBoard.type === "TGBT") && !(selectedFeeder?.downstream_board_id);

  return (
    <div className="page-stack" data-testid="architecture-screen">
      <PageHeader
        eyebrow="Architecture électrique · édition avancée"
        title="Du TGBT au récepteur."
        description="Commandes transactionnelles, déplacements contrôlés, duplication et historique de session. Chaque état est recalculé par le moteur Python avant publication."
        badge={<span className="outline-badge">Projet {project.state.dirty ? "modifié" : "enregistré"}</span>}
      />
      <section className="summary-grid summary-grid-compact">
        <SummaryCard label="Tableaux" value={String(project.project.board_count)} detail="TGBT et divisionnaires" icon="tree" tone="navy" />
        <SummaryCard label="Départs" value={String(project.project.feeder_count)} detail="Alimentation et charges" icon="bolt" tone="navy" />
        <SummaryCard label="Récepteurs" value={String(project.project.load_count)} detail="Affectés dans le projet" icon="file" tone="navy" />
        <SummaryCard label="Révision" value={String(project.state.revision)} detail={project.state.stale ? "Résultat à recalculer" : "Résultat à jour"} icon="engine" tone={project.state.stale ? "warn" : "ok"} />
      </section>
      <Toolbar
        left={
          <>
            <button type="button" className="button button-primary button-small" onClick={() => setDialog({ kind: "board", mode: "create" })} disabled={busy} data-testid="add-board">
              <Icon name="tree" size={14} /> Tableau
            </button>
            <button type="button" className="button button-secondary button-small" onClick={() => setDialog({ kind: "feeder", mode: "create" })} disabled={busy} data-testid="add-feeder">
              <Icon name="bolt" size={14} /> Départ
            </button>
            <button type="button" className="button button-secondary button-small" onClick={() => setDialog({ kind: "load", mode: "create" })} disabled={busy || project.feeders.length === 0} data-testid="add-load">
              <Icon name="file" size={14} /> Récepteur
            </button>
            <button
              type="button"
              className="button button-secondary button-small"
              onClick={() => {
                setError(null);
                setFeederLoadOpen(true);
              }}
              disabled={busy || !canCreatePair}
              title={selectedBoard ? "Créer un départ et son premier récepteur en une seule opération" : "Sélectionnez un tableau électrique compatible"}
              data-testid="add-feeder-load"
            >
              + Départ + Récepteur
            </button>
            <button type="button" className="button button-ghost button-small" onClick={() => setDialog({ kind: selectedKind ?? "load", mode: "edit" })} disabled={busy || !initial} data-testid="edit-entity">
              <Icon name="edit" size={14} /> Modifier
            </button>
            <button type="button" className="button button-ghost button-small" onClick={() => selectedKind && setActionDialog({ action: "move", kind: selectedKind })} disabled={busy || !canMove} data-testid="move-entity">
              <Icon name="arrow" size={14} /> Déplacer
            </button>
            <button type="button" className="button button-ghost button-small" onClick={() => selectedKind && setActionDialog({ action: "duplicate", kind: selectedKind })} disabled={busy || !canDuplicate} data-testid="duplicate-entity">
              <Icon name="file" size={14} /> Dupliquer
            </button>
            <button type="button" className="button button-ghost button-small" onClick={() => void openDelete()} disabled={busy || !initial} data-testid="delete-entity">
              <Icon name="close" size={14} /> Supprimer
            </button>
          </>
        }
        right={
          <>
            <span className="toolbar-count">{project.state.stale ? "Résultat périmé" : "Résultat à jour"}</span>
            <button type="button" className="button button-ghost button-small" onClick={onUndo} disabled={busy || historyBusy || !project.state.can_undo} title={project.state.undo_label ? `Annuler : ${project.state.undo_label}` : "Aucune annulation"} data-testid="undo-entity">
              <Icon name="reset" size={14} /> Annuler
            </button>
            <button type="button" className="button button-ghost button-small" onClick={onRedo} disabled={busy || historyBusy || !project.state.can_redo} title={project.state.redo_label ? `Rétablir : ${project.state.redo_label}` : "Aucun rétablissement"} data-testid="redo-entity">
              <Icon name="arrow" size={14} /> Rétablir
            </button>
            <button type="button" className="button button-ghost button-small" onClick={() => void run(() => recalculateProject(), "Bilan recalculé par le moteur.")} disabled={busy} data-testid="recalculate">
              <Icon name="reset" size={14} /> Recalculer
            </button>
          </>
        }
      />
      <SourcePanel project={project} onProjectChanged={onProjectChanged} onToast={onToast} />
      {error && <div className="inline-alert inline-alert-error"><Icon name="alert" size={16} /><span>{error}</span></div>}
      <div className={`architecture-layout ${view === "graph" ? "architecture-graph-layout" : ""}`}>
        <section className={`panel ${view === "tree" ? "tree-panel" : "graph-panel"}`} aria-label={view === "tree" ? "Arborescence électrique" : "Schéma électrique fonctionnel"}>
          <div className="panel-head">
            <div><span className="eyebrow">Explorateur</span><h2>{view === "tree" ? "Hiérarchie" : "Schéma graphique"}</h2></div>
            <span className="mini-badge">{project.project.board_count} tableaux</span>
          </div>
          <div className="toolbar toolbar-inside">
            <Tabs<"tree" | "graph">
              label="Vue de l’architecture"
              active={view}
              onChange={setView}
              items={[
                { id: "tree", label: "Arborescence", testId: "architecture-view-tree" },
                { id: "graph", label: "Schéma graphique", testId: "architecture-view-graph" },
              ]}
            />
            {view === "tree" && (
              <SearchInput label="Rechercher dans l’arborescence" value={search} onChange={setSearch} placeholder="Tableau, départ, récepteur…" testId="architecture-search" />
            )}
          </div>
          {view === "tree" ? (
            <div className="tree-scroll" tabIndex={0} role="region" aria-label="Arborescence électrique — zone défilante">
              <TreeView nodes={tree} selection={selection} onSelect={onSelect} search={search} emptyMessage="Aucun élément ne correspond à la recherche." ariaLabel="Arborescence électrique" />
            </div>
          ) : (
            <ElectricalGraphView key={`${project.project.id}:${project.state.revision}`} project={project} selection={selection} onSelect={onSelect} />
          )}
          <div className="panel-foot"><span className="muted-copy"><Icon name="lock" size={12} /> {view === "tree" ? "Aucune écriture sans sauvegarde." : "Lecture seule — navigation et sélection uniquement."}</span></div>
        </section>
        <section className="panel" aria-label="Propriétés de l’élément sélectionné" tabIndex={0} role="region">
          <PropertyContent project={project} selection={selection} temporaryEdits={temporaryEdits} onEditDesignation={onEditDesignation} onReset={onReset} />
        </section>
      </div>

      <EntityDialog
        open={dialog !== null}
        kind={dialog?.kind ?? "board"}
        mode={dialog?.mode ?? "create"}
        project={project}
        initial={initial}
        busy={busy}
        error={error}
        onSubmit={submitEntity}
        onClose={() => { setDialog(null); setError(null); }}
      />
      <FeederLoadDialog
        open={feederLoadOpen && Boolean(selectedBoard)}
        project={project}
        parentBoardId={selectedBoard?.id ?? ""}
        busy={busy}
        error={error}
        onSubmit={submitFeederLoad}
        onClose={() => {
          setFeederLoadOpen(false);
          setError(null);
        }}
      />
      <MoveDuplicateDialog
        open={actionDialog !== null}
        action={actionDialog?.action ?? "move"}
        kind={actionDialog?.kind ?? "board"}
        project={project}
        initial={initial}
        busy={busy}
        error={error}
        onSubmit={submitAction}
        onClose={() => { setActionDialog(null); setError(null); }}
      />
      <ConfirmDialog
        open={deleteTarget !== null}
        title="Supprimer cet élément ?"
        message={deleteTarget
          ? `Supprimer « ${deleteTarget.label} » ?\n${deleteTarget.preview.boards} tableau(x), ${deleteTarget.preview.feeders} départ(s), ${deleteTarget.preview.loads} récepteur(s) seront concernés.${deleteTarget.preview.descendants.length ? `\nDescendants : ${deleteTarget.preview.descendants.join(", ")}.` : ""}\nCette suppression est explicite et annulable.`
          : ""}
        confirmLabel="Supprimer avec confirmation"
        danger
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
