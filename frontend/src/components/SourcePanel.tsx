import { useState } from "react";
import {
  ApiError,
  deleteProjectSource,
  updateProjectSource,
} from "../api";
import { ConfirmDialog } from "./ConfirmDialog";
import { SourceDialog } from "./SourceDialog";
import type { ProjectPayload, SourcePayload, SourceType } from "../types";

const SOURCE_LABELS: Record<SourceType, string> = {
  AC_THREE_PHASE: "Source AC triphasée",
  AC_SINGLE_PHASE: "Source AC monophasée",
  DC: "Source DC",
  ENEDIS: "Souscription Enedis",
  TRANSFORMER: "Transformateur HTA/BT",
  GENERATOR: "Groupe électrogène",
  BATTERY: "Batterie",
};

function errorText(error: unknown): string {
  return error instanceof ApiError || error instanceof Error
    ? error.message
    : "Opération source impossible.";
}

function sourceDetails(source: SourcePayload): string {
  const parts: string[] = [];
  if (source.rated_power) parts.push(`${source.rated_power} ${source.rated_power_unit}`);
  if (source.active_power) parts.push(`${source.active_power} ${source.active_power_unit}`);
  if (source.nominal_voltage) parts.push(`${source.nominal_voltage} ${source.voltage_unit}`);
  if (source.frequency_hz) parts.push(`${source.frequency_hz} Hz`);
  if (source.power_factor) parts.push(`cos φ ${source.power_factor}`);
  if (source.phase_system) parts.push(source.phase_system);
  return parts.join(" · ");
}

export function SourcePanel({
  project,
  onProjectChanged,
  onToast,
}: {
  project: ProjectPayload;
  onProjectChanged: (project: ProjectPayload) => void;
  onToast: (message: string, tone: "info" | "success" | "warning" | "error") => void;
}) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const source = project.source ?? null;

  const save = async (payload: SourcePayload) => {
    setBusy(true);
    setError(null);
    try {
      const updated = await updateProjectSource(payload, project.state.revision);
      onProjectChanged(updated);
      setDialogOpen(false);
      onToast("Source électrique enregistrée.", "success");
    } catch (caught) {
      const message = errorText(caught);
      setError(message);
      onToast(message, "error");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    setError(null);
    try {
      const updated = await deleteProjectSource(project.state.revision);
      onProjectChanged(updated);
      setDeleteOpen(false);
      onToast("Source électrique supprimée.", "success");
    } catch (caught) {
      const message = errorText(caught);
      setError(message);
      onToast(message, "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel source-panel" data-testid="source-panel">
      <div className="panel-head">
        <div>
          <span className="eyebrow">Projet · source électrique</span>
          <h2>Source d'alimentation</h2>
        </div>
        <div className="source-actions">
          {source && (
            <button
              type="button"
              className="button button-ghost button-small"
              onClick={() => setDeleteOpen(true)}
              disabled={busy}
              data-testid="source-delete"
            >
              Supprimer
            </button>
          )}
          <button
            type="button"
            className="button button-primary button-small"
            onClick={() => setDialogOpen(true)}
            disabled={busy}
            data-testid="source-edit"
          >
            {source ? "Modifier" : "Configurer une source"}
          </button>
        </div>
      </div>
      {error && <div className="inline-alert inline-alert-error">{error}</div>}
      {source ? (
        <div className="source-summary" data-testid="source-summary">
          <div>
            <strong>{SOURCE_LABELS[source.source_type] ?? source.source_type}</strong>
            <span>{source.reference} · {source.designation}</span>
          </div>
          <span className="muted-copy">{sourceDetails(source)}</span>
        </div>
      ) : (
        <div className="inline-alert inline-alert-warning">
          Aucune source électrique configurée. Le projet reste calculable avec
          les données électriques existantes.
        </div>
      )}
      <SourceDialog
        open={dialogOpen}
        initial={source}
        busy={busy}
        error={error}
        onSubmit={save}
        onClose={() => {
          setDialogOpen(false);
          setError(null);
        }}
      />
      <ConfirmDialog
        open={deleteOpen}
        title="Supprimer la source électrique ?"
        message="La source unique du projet sera supprimée explicitement. Cette action est annulable."
        confirmLabel="Supprimer la source"
        danger
        onConfirm={remove}
        onCancel={() => setDeleteOpen(false)}
      />
    </section>
  );
}
