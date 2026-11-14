import { Icon } from "../icons";
import { Breadcrumb } from "./Breadcrumb";

export function Topbar({
  breadcrumb,
  projectName,
  projectReference,
  engineVersion,
  dirty,
  readOnly,
  saving,
  saveError,
  theme,
  onToggleTheme,
  onSave,
}: {
  breadcrumb: string[];
  projectName: string;
  projectReference: string;
  engineVersion: string;
  dirty: boolean;
  readOnly: boolean;
  saving: boolean;
  saveError: boolean;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onSave: () => void;
}) {
  return (
    <header className="topbar">
      <Breadcrumb items={breadcrumb} />
      <div className="topbar-actions">
        <div className="context-project" title={projectName}>
          <span className="context-label">Projet</span>
          <strong>{projectReference || projectName || "—"}</strong>
        </div>
        <div className={`dirty-indicator ${dirty ? "is-dirty" : ""} ${saveError ? "is-error" : ""}`}>
          <span className="dot" />
          {readOnly ? "Lecture seule" : saving ? "Enregistrement…" : saveError ? "Erreur de sauvegarde" : dirty ? "Non enregistré" : "Enregistré"}
        </div>
        {dirty && !readOnly && (
          <button type="button" className="icon-button" onClick={onSave} title="Enregistrer" aria-label="Enregistrer le projet" data-testid="topbar-save">
            <Icon name="check" size={16} />
          </button>
        )}
        <div className="engine-pill" title="Moteur Python local en lecture seule">
          <span className="pulse" />
          <span>Moteur</span>
          <strong>{engineVersion}</strong>
        </div>
        <button
          type="button"
          className="icon-button"
          onClick={onToggleTheme}
          aria-label={theme === "light" ? "Activer le mode sombre" : "Activer le mode clair"}
          title={theme === "light" ? "Mode sombre" : "Mode clair"}
        >
          <Icon name={theme === "light" ? "moon" : "sun"} />
        </button>
        <div className="user-chip" title="Session locale de qualification">
          <span className="avatar">ST</span>
          <span className="user-text">Qualification</span>
        </div>
      </div>
    </header>
  );
}
