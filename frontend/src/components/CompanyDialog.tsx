import { useEffect, useState } from "react";
import { fetchCompanyLogo } from "../api";
import type { CompanyProfile } from "../types";
import { FormModal } from "./FormModal";

type CompanyFormState = Omit<CompanyProfile, "logo">;

function initialState(profile?: CompanyProfile | null): CompanyFormState {
  return {
    legal_name: profile?.legal_name ?? "",
    trade_name: profile?.trade_name ?? "",
    address_line1: profile?.address_line1 ?? "",
    address_line2: profile?.address_line2 ?? "",
    postal_code: profile?.postal_code ?? "",
    city: profile?.city ?? "",
    country: profile?.country ?? "",
    phone: profile?.phone ?? "",
    email: profile?.email ?? "",
    website: profile?.website ?? "",
    siren: profile?.siren ?? "",
    siret: profile?.siret ?? "",
    vat_number: profile?.vat_number ?? "",
    manager_name: profile?.manager_name ?? "",
    manager_role: profile?.manager_role ?? "",
    document_footer: profile?.document_footer ?? "",
  };
}

export function CompanyDialog({
  open,
  initial,
  busy,
  error,
  onSubmit,
  onClose,
}: {
  open: boolean;
  initial?: CompanyProfile | null;
  busy: boolean;
  error: string | null;
  onSubmit: (payload: CompanyProfile, logoFile: File | null, removeLogo: boolean) => void;
  onClose: () => void;
}) {
  const [form, setForm] = useState<CompanyFormState>(() => initialState(initial));
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [removeLogo, setRemoveLogo] = useState(false);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [logoError, setLogoError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setForm(initialState(initial));
    setLogoFile(null);
    setRemoveLogo(false);
    setLogoError(null);
    setLogoPreview(null);
    let active = true;
    let objectUrl: string | null = null;
    if (initial?.logo) {
      void fetchCompanyLogo()
        .then((url) => {
          if (!active) {
            if (url) URL.revokeObjectURL(url);
            return;
          }
          objectUrl = url;
          setLogoPreview(url);
        })
        .catch(() => {
          if (active) setLogoError("Le logo existant n'a pas pu être chargé.");
        });
    }
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [open, initial]);

  useEffect(() => {
    return () => {
      if (logoPreview?.startsWith("blob:")) URL.revokeObjectURL(logoPreview);
    };
  }, [logoPreview]);

  const set = <K extends keyof CompanyFormState>(key: K, value: CompanyFormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const selectLogo = (file: File | null) => {
    setLogoError(null);
    setRemoveLogo(false);
    setLogoFile(file);
    setLogoPreview((current) => {
      if (current?.startsWith("blob:")) URL.revokeObjectURL(current);
      return file && typeof URL.createObjectURL === "function" ? URL.createObjectURL(file) : null;
    });
  };

  const clearLogo = () => {
    setLogoFile(null);
    setRemoveLogo(true);
    setLogoPreview((current) => {
      if (current?.startsWith("blob:")) URL.revokeObjectURL(current);
      return null;
    });
  };

  return (
    <FormModal
      open={open}
      title="Mon entreprise"
      description="Identité administrative locale utilisée dans les documents. Aucun profil n'est imposé."
      onClose={onClose}
      testId="company-dialog"
      wide
      footer={
        <>
          <button type="button" className="button button-ghost" onClick={onClose} disabled={busy}>
            Annuler
          </button>
          <button
            type="button"
            className="button button-primary"
            disabled={busy || !form.legal_name.trim()}
            onClick={() => onSubmit({ ...form, logo: initial?.logo ?? null }, logoFile, removeLogo)}
            data-testid="company-save"
          >
            {busy ? "Enregistrement…" : "Enregistrer"}
          </button>
        </>
      }
    >
      {error && <div className="inline-alert inline-alert-error">{error}</div>}
      {logoError && <div className="inline-alert inline-alert-error">{logoError}</div>}

      <div className="form-grid">
        <label>
          <span>Raison sociale *</span>
          <input value={form.legal_name} onChange={(event) => set("legal_name", event.target.value)} data-testid="company-legal-name" />
        </label>
        <label>
          <span>Nom commercial</span>
          <input value={form.trade_name} onChange={(event) => set("trade_name", event.target.value)} data-testid="company-trade-name" />
        </label>

        <div className="wide-field client-logo-field">
          <span>Logo de l'entreprise</span>
          <div className="client-logo-controls">
            {logoPreview ? (
              <img className="client-logo-preview" src={logoPreview} alt="Logo de l'entreprise" data-testid="company-logo-preview" />
            ) : (
              <div className="client-logo-placeholder" aria-hidden="true">Logo</div>
            )}
            <div className="client-logo-actions">
              <label className="button button-ghost button-small">
                Choisir un logo
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  className="visually-hidden"
                  onChange={(event) => selectLogo(event.target.files?.[0] ?? null)}
                  data-testid="company-logo-input"
                />
              </label>
              {(logoPreview || initial?.logo) && !removeLogo && (
                <button type="button" className="button button-ghost button-small" onClick={clearLogo} data-testid="company-logo-remove">
                  Supprimer le logo
                </button>
              )}
              {removeLogo && <span className="muted-copy">Le logo sera supprimé.</span>}
            </div>
          </div>
          <p className="form-note">PNG, JPEG ou WebP — 5 Mo maximum — 4096 px maximum.</p>
        </div>

        <label className="wide-field">
          <span>Adresse ligne 1</span>
          <input value={form.address_line1} onChange={(event) => set("address_line1", event.target.value)} data-testid="company-address-line1" />
        </label>
        <label className="wide-field">
          <span>Adresse ligne 2</span>
          <input value={form.address_line2} onChange={(event) => set("address_line2", event.target.value)} data-testid="company-address-line2" />
        </label>
        <label>
          <span>Code postal</span>
          <input value={form.postal_code} onChange={(event) => set("postal_code", event.target.value)} data-testid="company-postal-code" />
        </label>
        <label>
          <span>Ville</span>
          <input value={form.city} onChange={(event) => set("city", event.target.value)} data-testid="company-city" />
        </label>
        <label>
          <span>Pays</span>
          <input value={form.country} onChange={(event) => set("country", event.target.value)} data-testid="company-country" />
        </label>
        <label>
          <span>Téléphone</span>
          <input value={form.phone} onChange={(event) => set("phone", event.target.value)} data-testid="company-phone" />
        </label>
        <label>
          <span>E-mail</span>
          <input type="email" value={form.email} onChange={(event) => set("email", event.target.value)} data-testid="company-email" />
        </label>
        <label>
          <span>Site internet</span>
          <input value={form.website} onChange={(event) => set("website", event.target.value)} placeholder="https://" data-testid="company-website" />
        </label>
        <label>
          <span>SIREN</span>
          <input value={form.siren} onChange={(event) => set("siren", event.target.value)} data-testid="company-siren" />
        </label>
        <label>
          <span>SIRET</span>
          <input value={form.siret} onChange={(event) => set("siret", event.target.value)} data-testid="company-siret" />
        </label>
        <label>
          <span>TVA intracommunautaire</span>
          <input value={form.vat_number} onChange={(event) => set("vat_number", event.target.value)} data-testid="company-vat" />
        </label>
        <label>
          <span>Responsable</span>
          <input value={form.manager_name} onChange={(event) => set("manager_name", event.target.value)} data-testid="company-manager-name" />
        </label>
        <label>
          <span>Fonction</span>
          <input value={form.manager_role} onChange={(event) => set("manager_role", event.target.value)} data-testid="company-manager-role" />
        </label>
        <label className="wide-field">
          <span>Texte de pied de page</span>
          <textarea rows={2} value={form.document_footer} onChange={(event) => set("document_footer", event.target.value)} data-testid="company-footer" />
        </label>
      </div>
    </FormModal>
  );
}
