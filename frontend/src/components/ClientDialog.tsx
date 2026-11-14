import { useEffect, useState } from "react";
import { fetchClientLogo } from "../api";
import type { Client } from "../types";
import { FormModal } from "./FormModal";

type ClientFormState = {
  company_name: string;
  address: string;
  address_line1: string;
  address_line2: string;
  postal_code: string;
  city: string;
  country: string;
  contact_name: string;
  email: string;
  phone: string;
};

function initialState(client?: Client | null): ClientFormState {
  return {
    company_name: client?.company_name ?? "",
    address: client?.address ?? "",
    address_line1: client?.address_line1 ?? "",
    address_line2: client?.address_line2 ?? "",
    postal_code: client?.postal_code ?? "",
    city: client?.city ?? "",
    country: client?.country ?? "",
    contact_name: client?.contact_name ?? "",
    email: client?.email ?? "",
    phone: client?.phone ?? "",
  };
}

export function ClientDialog({
  open,
  mode,
  initial,
  busy,
  error,
  onSubmit,
  onClose,
}: {
  open: boolean;
  mode: "create" | "edit";
  initial?: Client | null;
  busy: boolean;
  error: string | null;
  onSubmit: (
    payload: Record<string, unknown>,
    logoFile: File | null,
    removeLogo: boolean,
  ) => void;
  onClose: () => void;
}) {
  const [form, setForm] = useState<ClientFormState>(() => initialState(initial));
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
    if (initial?.id && initial.logo) {
      void fetchClientLogo(initial.id)
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

  const set = <K extends keyof ClientFormState>(key: K, value: ClientFormState[K]) => {
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
      title={mode === "create" ? "Créer un client" : "Modifier le client"}
      description="Les coordonnées du client sont conservées dans le référentiel local. Les projets associés gardent leur snapshot."
      onClose={onClose}
      testId="client-dialog"
      wide
      footer={
        <>
          <button type="button" className="button button-ghost" onClick={onClose} disabled={busy}>
            Annuler
          </button>
          <button
            type="button"
            className="button button-primary"
            disabled={busy || !form.company_name.trim()}
            onClick={() => onSubmit(form, logoFile, removeLogo)}
            data-testid="client-save"
          >
            {busy ? "Enregistrement…" : mode === "create" ? "Créer le client" : "Enregistrer"}
          </button>
        </>
      }
    >
      {error && <div className="inline-alert inline-alert-error">{error}</div>}
      {logoError && <div className="inline-alert inline-alert-error">{logoError}</div>}
      <div className="form-grid">
        <label>
          <span>Raison sociale *</span>
          <input
            value={form.company_name}
            onChange={(event) => set("company_name", event.target.value)}
            data-testid="client-company-name"
          />
        </label>
        <label>
          <span>Pays</span>
          <input value={form.country} onChange={(event) => set("country", event.target.value)} data-testid="client-country" />
        </label>

        <div className="wide-field client-logo-field" data-testid="client-logo-field">
          <span>Logo client</span>
          <div className="client-logo-controls">
            {logoPreview ? (
              <img className="client-logo-preview" src={logoPreview} alt="Logo du client" data-testid="client-logo-preview" />
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
                  data-testid="client-logo-input"
                />
              </label>
              {(logoPreview || initial?.logo) && !removeLogo && (
                <button type="button" className="button button-ghost button-small" onClick={clearLogo} data-testid="client-logo-remove">
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
          <input
            value={form.address_line1}
            onChange={(event) => set("address_line1", event.target.value)}
            data-testid="client-address-line1"
          />
        </label>
        <label className="wide-field">
          <span>Adresse ligne 2</span>
          <input
            value={form.address_line2}
            onChange={(event) => set("address_line2", event.target.value)}
            data-testid="client-address-line2"
          />
        </label>
        <label>
          <span>Code postal</span>
          <input value={form.postal_code} onChange={(event) => set("postal_code", event.target.value)} data-testid="client-postal-code" />
        </label>
        <label>
          <span>Ville</span>
          <input value={form.city} onChange={(event) => set("city", event.target.value)} data-testid="client-city" />
        </label>

        {initial?.address && (
          <label className="wide-field">
            <span>Adresse historique conservée</span>
            <textarea
              rows={2}
              value={form.address}
              onChange={(event) => set("address", event.target.value)}
              data-testid="client-address"
            />
          </label>
        )}

        <label>
          <span>Contact général</span>
          <input
            value={form.contact_name}
            onChange={(event) => set("contact_name", event.target.value)}
            data-testid="client-contact"
          />
        </label>
        <label>
          <span>Téléphone général</span>
          <input value={form.phone} onChange={(event) => set("phone", event.target.value)} data-testid="client-phone" />
        </label>
        <label>
          <span>E-mail général</span>
          <input
            type="email"
            value={form.email}
            onChange={(event) => set("email", event.target.value)}
            data-testid="client-email"
          />
        </label>
      </div>
    </FormModal>
  );
}
