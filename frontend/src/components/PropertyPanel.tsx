import { useEffect, useState, type ReactNode } from "react";
import { Icon } from "../icons";
import type { Diagnostic } from "../types";
import { EmptyState } from "./EmptyState";
import { StatusIndicator } from "./StatusIndicator";

export type PropertySection = {
  title: string;
  rows: Array<{ label: string; value: ReactNode }>;
};

export function PropertyPanel({
  title,
  subtitle,
  badge,
  status,
  sections,
  diagnostics,
  assumptions,
  designation,
  modified = false,
  onEditDesignation,
  onReset,
  testId = "property-panel",
}: {
  title?: string;
  subtitle?: string;
  badge?: string;
  status?: string;
  sections?: PropertySection[];
  diagnostics?: Diagnostic[];
  assumptions?: string[];
  designation?: string;
  modified?: boolean;
  onEditDesignation?: (value: string) => void;
  onReset?: () => void;
  testId?: string;
}) {
  const [draft, setDraft] = useState(designation ?? "");
  useEffect(() => setDraft(designation ?? ""), [designation, title]);

  if (!title) {
    return (
      <EmptyState
        icon="tree"
        title="Aucune sélection"
        description="Sélectionnez un tableau, un départ ou un récepteur pour afficher ses propriétés."
      />
    );
  }

  return (
    <div className="property-panel" data-testid={testId}>
      <div className="property-head">
        <div>
          {badge && <span className="badge badge-navy">{badge}</span>}
          <h2>{title}</h2>
          {subtitle && <span className="mono property-subtitle">{subtitle}</span>}
        </div>
        {status && <StatusIndicator status={status} compact />}
      </div>

      {onEditDesignation && (
        <div className={`temporary-edit ${modified ? "is-modified" : ""}`}>
          <div className="temporary-edit-label">
            <span><Icon name="edit" size={13} /> Désignation</span>
            {modified && <span className="temporary-badge">Non enregistrée</span>}
          </div>
          <div className="temporary-edit-row">
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") onEditDesignation(draft);
              }}
              aria-label="Désignation"
            />
            <button type="button" className="button button-secondary button-small" onClick={() => onEditDesignation(draft)}>
              Appliquer
            </button>
            {modified && onReset && (
              <button type="button" className="icon-button icon-button-small" onClick={onReset} title="Annuler la modification">
                <Icon name="reset" size={14} />
              </button>
            )}
          </div>
          <small>Modification locale : enregistrez le projet pour la conserver.</small>
        </div>
      )}

      {sections?.map((section) => (
        <section key={section.title} className="property-section">
          <h3>{section.title}</h3>
          <dl className="property-list">
            {section.rows.map((row) => (
              <div key={row.label}>
                <dt>{row.label}</dt>
                <dd>{row.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      ))}

      {diagnostics && diagnostics.length > 0 && (
        <section className="property-section">
          <h3>Diagnostics</h3>
          <div className="diagnostics-list">
            {diagnostics.map((diagnostic) => (
              <div key={`${diagnostic.code}-${diagnostic.field ?? ""}`} className={`diagnostic diagnostic-${diagnostic.severity}`}>
                <Icon name={diagnostic.severity === "error" ? "alert" : "info"} size={13} />
                <div><strong>{diagnostic.code}</strong><span>{diagnostic.message}</span></div>
              </div>
            ))}
          </div>
        </section>
      )}

      {assumptions && assumptions.length > 0 && (
        <section className="property-section assumptions">
          <h3>Hypothèses du moteur</h3>
          <ul>{assumptions.map((assumption) => <li key={assumption}>{assumption}</li>)}</ul>
        </section>
      )}
    </div>
  );
}
