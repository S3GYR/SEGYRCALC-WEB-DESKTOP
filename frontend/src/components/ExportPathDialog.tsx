import { useEffect, useState } from "react";
import { FormModal } from "./FormModal";

export function ExportPathDialog({
  open,
  format,
  initialPath,
  root,
  busy,
  error,
  onSubmit,
  onClose,
}: {
  open: boolean;
  format: "pdf" | "xlsx" | "csv";
  initialPath: string;
  root: string;
  busy: boolean;
  error: string | null;
  onSubmit: (path: string, overwrite: boolean) => void;
  onClose: () => void;
}) {
  const [path, setPath] = useState(initialPath);
  const [overwrite, setOverwrite] = useState(false);
  useEffect(() => {
    if (open) {
      setPath(initialPath);
      setOverwrite(false);
    }
  }, [open, initialPath]);

  const isCsv = format === "csv";
  return (
    <FormModal
      open={open}
      title={isCsv ? "Exporter les CSV" : `Exporter le rapport ${format.toUpperCase()}`}
      description="Le fichier est écrit dans le répertoire d’export isolé après validation du snapshot."
      onClose={onClose}
      testId="export-path-dialog"
      footer={
        <>
          <button type="button" className="button button-ghost" onClick={onClose} disabled={busy}>
            Annuler
          </button>
          <button
            type="button"
            className="button button-primary"
            disabled={busy || !path.trim()}
            onClick={() => onSubmit(path.trim(), overwrite)}
            data-testid="export-confirm"
          >
            {busy ? "Export en cours…" : "Exporter"}
          </button>
        </>
      }
    >
      {error && <div className="inline-alert inline-alert-error" role="alert">{error}</div>}
      <label className="path-field">
        <span>{isCsv ? "Répertoire de destination" : "Chemin du fichier"}</span>
        <input
          value={path}
          onChange={(event) => setPath(event.target.value)}
          data-testid="export-path-input"
          spellCheck={false}
        />
      </label>
      <p className="form-note">
        Répertoire autorisé : <span className="mono">{root}</span>
        {isCsv
          ? " · six fichiers CSV seront créés : synthèse, tableaux, départs, récepteurs, phases et traçabilité."
          : ` · extension ${format === "pdf" ? ".pdf" : ".xlsx"} obligatoire.`}
      </p>
      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={overwrite}
          onChange={(event) => setOverwrite(event.target.checked)}
          data-testid="export-overwrite"
        />
        Autoriser le remplacement d’un fichier existant
      </label>
      <p className="form-note">
        Sans cette case, aucun fichier existant n’est écrasé. Les CSV sont écrits fichier par fichier après validation.
      </p>
    </FormModal>
  );
}
