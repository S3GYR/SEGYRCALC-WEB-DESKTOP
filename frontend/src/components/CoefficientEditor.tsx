import { useEffect, useState } from "react";
import { formatNumber } from "../format";
import { Icon } from "../icons";
import type { ProjectPayload, Selection } from "../types";

export function CoefficientEditor({
  project,
  selection,
  onEditCoefficient,
}: {
  project: ProjectPayload;
  selection: Selection | null;
  onEditCoefficient: (kind: "load" | "feeder", id: string, value: string) => void;
}) {
  const load = selection?.kind === "load" ? project.loads.find((item) => item.id === selection.id) ?? null : null;
  const feeder = selection?.kind === "feeder" ? project.feeders.find((item) => item.id === selection.id) ?? null : null;
  const editable = load ?? feeder ?? null;
  const kind = load ? "load" : feeder ? "feeder" : null;
  const initial = load ? load.ku : feeder?.ks ?? "";
  const [value, setValue] = useState(initial);
  useEffect(() => setValue(initial), [initial, selection?.id]);

  if (!editable || !kind) {
    return (
      <section className="panel coefficient-panel" data-testid="coefficient-panel">
        <div className="panel-head"><div><span className="eyebrow">Coefficients</span><h3>Ku / Ks</h3></div></div>
        <p className="muted-copy">Sélectionnez un récepteur pour Ku ou un départ pour Ks. Aucune propagation n’est inventée dans l’interface.</p>
      </section>
    );
  }

  return (
    <section className="panel coefficient-panel" data-testid="coefficient-panel">
      <div className="panel-head">
        <div><span className="eyebrow">Coefficients</span><h3>{kind === "load" ? "Ku du récepteur" : "Ks du départ"}</h3></div>
        <span className="mini-badge">{editable.designation}</span>
      </div>
      <div className="coefficient-grid">
        <label>
          <span>{kind === "load" ? "Ku" : "Ks"}</span>
          <input
            value={value}
            onChange={(event) => setValue(event.target.value)}
            inputMode="decimal"
            data-testid="coefficient-input"
            disabled={project.state.read_only_source}
          />
        </label>
        <div className="coefficient-meta">
          <span>Valeur actuelle <b>{formatNumber(initial)}</b></span>
          <span>{kind === "load" ? "Ks appliqué au départ" : "Ku appliqué aux récepteurs"} <b>{kind === "load" ? formatNumber(load?.ks) : "niveau récepteur"}</b></span>
        </div>
        <button
          type="button"
          className="button button-primary button-small"
          disabled={project.state.read_only_source || busyValue(value, initial)}
          onClick={() => onEditCoefficient(kind, editable.id, value)}
          data-testid="coefficient-apply"
        >
          <Icon name="check" size={14} /> Appliquer et recalculer
        </button>
      </div>
      <p className="form-note">La commande transactionnelle WEB-05 vérifie la révision, recalcule le moteur puis publie le nouvel état. Annuler/Rétablir reste disponible.</p>
    </section>
  );
}

function busyValue(value: string, initial: string): boolean {
  const normalized = value.trim().replace(",", ".");
  return !normalized || normalized === initial;
}
