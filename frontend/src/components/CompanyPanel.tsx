import { useEffect, useState } from "react";
import {
  ApiError,
  deleteCompanyLogo,
  fetchCompanyLogo,
  getCompany,
  updateCompany,
  uploadCompanyLogo,
} from "../api";
import type { CompanyPayload, CompanyProfile } from "../types";
import { CompanyDialog } from "./CompanyDialog";

function errorText(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "Opération entreprise impossible.";
}

function formatAddress(company: CompanyProfile): string {
  return [
    company.address_line1,
    company.address_line2,
    [company.postal_code, company.city].filter(Boolean).join(" "),
    company.country,
  ]
    .filter(Boolean)
    .join("\n");
}

export function CompanyPanel() {
  const [data, setData] = useState<CompanyPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void getCompany()
      .then((payload) => {
        if (active) setData(payload);
      })
      .catch((caught) => {
        if (active) setError(errorText(caught));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;
    setLogoPreview((current) => {
      if (current?.startsWith("blob:")) URL.revokeObjectURL(current);
      return null;
    });
    if (data?.company.logo) {
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
          if (active) setError("Le logo de l'entreprise n'a pas pu être chargé.");
        });
    }
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [data?.company.logo]);

  const submit = async (
    payload: CompanyProfile,
    logoFile: File | null,
    removeLogo: boolean,
  ) => {
    setBusy(true);
    setFormError(null);
    try {
      let result = await updateCompany(payload);
      if (logoFile) {
        result = await uploadCompanyLogo(logoFile);
      } else if (removeLogo && result.company.logo) {
        result = await deleteCompanyLogo();
      }
      setData(result);
      setDialogOpen(false);
      setError(null);
    } catch (caught) {
      setFormError(errorText(caught));
    } finally {
      setBusy(false);
    }
  };

  const company = data?.company ?? null;
  const configured = Boolean(data?.configured);

  return (
    <section className="panel company-panel" data-testid="company-panel">
      <div className="panel-head">
        <div>
          <span className="eyebrow">Paramètres</span>
          <h2>Mon entreprise</h2>
        </div>
        <button
          type="button"
          className="button button-primary button-small"
          onClick={() => {
            setFormError(null);
            setDialogOpen(true);
          }}
          data-testid="company-edit"
        >
          {configured ? "Modifier" : "Configurer mon entreprise"}
        </button>
      </div>

      {loading && <p className="muted-copy">Chargement du profil entreprise…</p>}
      {error && <div className="inline-alert inline-alert-error">{error}</div>}
      {!loading && !configured && (
        <div className="inline-alert inline-alert-warning">
          Entreprise non configurée. Les exports restent possibles, mais les
          documents ne pourront pas reprendre l'identité de l'entreprise.
        </div>
      )}

      {company && configured && (
        <div className="company-summary" data-testid="company-summary">
          <div className="company-summary-main">
            {logoPreview ? (
              <img className="company-logo" src={logoPreview} alt="Logo de l'entreprise" data-testid="company-logo" />
            ) : (
              <div className="company-logo company-logo-placeholder" aria-hidden="true">Logo</div>
            )}
            <div>
              <strong>{company.legal_name}</strong>
              {company.trade_name && <span>{company.trade_name}</span>}
              <span>{formatAddress(company)}</span>
            </div>
          </div>
          <dl className="info-list">
            <div><dt>Téléphone</dt><dd>{company.phone || "—"}</dd></div>
            <div><dt>E-mail</dt><dd>{company.email || "—"}</dd></div>
            <div><dt>Site internet</dt><dd>{company.website || "—"}</dd></div>
            <div><dt>SIREN</dt><dd className="mono">{company.siren || "—"}</dd></div>
            <div><dt>SIRET</dt><dd className="mono">{company.siret || "—"}</dd></div>
            <div><dt>TVA intracommunautaire</dt><dd className="mono">{company.vat_number || "—"}</dd></div>
            <div><dt>Responsable</dt><dd>{company.manager_name || "—"}{company.manager_role ? ` · ${company.manager_role}` : ""}</dd></div>
          </dl>
        </div>
      )}

      {company && configured && company.document_footer && (
        <p className="form-note company-footer-note">{company.document_footer}</p>
      )}

      <CompanyDialog
        open={dialogOpen}
        initial={company}
        busy={busy}
        error={formError}
        onSubmit={submit}
        onClose={() => setDialogOpen(false)}
      />
    </section>
  );
}
