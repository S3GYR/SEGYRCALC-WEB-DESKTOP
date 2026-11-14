import { useEffect, useState } from "react";
import { FormModal } from "./FormModal";

export function PathDialog({
  open,
  mode,
  initialPath,
  busy,
  error,
  onSubmit,
  onClose,
}: {
  open: boolean;
  mode: "open" | "save" | "duplicate";
  initialPath: string;
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

  return (
    <FormModal
      open={open}
      title={mode === "open" ? "Ouvrir un projet" : mode === "duplicate" ? "Dupliquer le projet" : "Enregistrer le projet sous"}
      description="Les écritures sont limitées au répertoire de qualification isolé. Les fichiers historiques restent en lecture seule."
      onClose={onClose}
      testId="path-dialog"
      footer={
        <>
          <button type="button" className="button button-ghost" onClick={onClose} disabled={busy}>Annuler</button>
          <button type="button" className="button button-primary" disabled={busy || !path.trim()} onClick={() => onSubmit(path.trim(), overwrite)}>
            {busy ? "Traitement…" : mode === "open" ? "Ouvrir" : mode === "duplicate" ? "Dupliquer" : "Enregistrer"}
          </button>
        </>
      }
    >
      {error && <div className="inline-alert inline-alert-error">{error}</div>}
      <label className="path-field">
        <span>Chemin du fichier</span>
        <input value={path} onChange={(event) => setPath(event.target.value)} data-testid="path-input" />
      </label>
      {mode !== "open" && (
        <label className="checkbox-label"><input type="checkbox" checked={overwrite} onChange={(event) => setOverwrite(event.target.checked)} /> Autoriser le remplacement d'un fichier existant</label>
      )}
      <p className="form-note">Format WEB-03 conservé : <span className="mono">.segyrcalc-web.json</span>. Les fichiers V1.3/V1.4 s'ouvrent en lecture seule et doivent être enregistrés sous un nouveau nom.</p>
    </FormModal>
  );
}
