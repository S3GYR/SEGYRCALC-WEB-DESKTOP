import { useEffect, useState } from "react";
import { ApiError, createClient, uploadClientLogo } from "../api";
import type { Client, ProjectPayload } from "../types";
import { ClientDialog } from "./ClientDialog";
import { FormModal } from "./FormModal";

type FormState = {
  name: string;
  reference: string;
  client: string;
  client_id: string | null;
  site: string;
  address: string;
  author: string;
  description: string;
  observations: string;
  revision: string;
  network: "MONO" | "TRI";
  voltage_v: string;
  has_neutral: boolean;
  voltage_ln_v: string;
};

function initial(project?: ProjectPayload | null): FormState {
  return {
    name: project?.project.name ?? "",
    reference: project?.project.reference ?? "",
    client: project?.project.client ?? "",
    client_id: project?.project.client_id ?? null,
    site: project?.web.site ?? "",
    address: project?.web.address ?? "",
    author: project?.web.created_by ?? "",
    description: project?.project.description ?? "",
    observations: project?.web.observations ?? "",
    revision: "A",
    network: "TRI",
    voltage_v: "400",
    has_neutral: true,
    voltage_ln_v: "230",
  };
}

function errorText(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : "Création du client impossible.";
}

export function ProjectFormDialog({
  open,
  mode,
  project,
  clients,
  busy,
  error,
  onSubmit,
  onClose,
  onClientsChanged,
}: {
  open: boolean;
  mode: "create" | "edit";
  project?: ProjectPayload | null;
  clients?: Client[];
  busy: boolean;
  error: string | null;
  onSubmit: (payload: Record<string, unknown>) => void;
  onClose: () => void;
  onClientsChanged?: () => void;
}) {
  const [form, setForm] = useState<FormState>(() => initial(project));
  const [availableClients, setAvailableClients] = useState<Client[]>(clients ?? []);
  const [clientDialogOpen, setClientDialogOpen] = useState(false);
  const [clientBusy, setClientBusy] = useState(false);
  const [clientError, setClientError] = useState<string | null>(null);
  const [refreshClient, setRefreshClient] = useState(false);

  useEffect(() => {
    if (open) {
      setForm(initial(project));
      setRefreshClient(false);
    }
  }, [open, project]);

  useEffect(() => {
    setAvailableClients(clients ?? []);
  }, [clients]);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const selectedClient = form.client_id
    ? availableClients.find((client) => client.id === form.client_id) ?? null
    : null;

  const selectClient = (clientId: string) => {
    const client = availableClients.find((item) => item.id === clientId);
    setRefreshClient(false);
    setForm((current) => ({
      ...current,
      client_id: client?.id ?? null,
      client: client?.company_name ?? "",
    }));
  };

  const submitClient = async (
    payload: Record<string, unknown>,
    logoFile: File | null,
    _removeLogo: boolean,
  ) => {
    setClientBusy(true);
    setClientError(null);
    try {
      let client = await createClient(payload);
      if (logoFile) client = await uploadClientLogo(client.id, logoFile);
      setAvailableClients((current) => [...current, client].sort((a, b) => a.company_name.localeCompare(b.company_name)));
      setForm((current) => ({
        ...current,
        client_id: client.id,
        client: client.company_name,
      }));
      setClientDialogOpen(false);
      onClientsChanged?.();
    } catch (caught) {
      setClientError(errorText(caught));
    } finally {
      setClientBusy(false);
    }
  };

  return (
    <>
      <FormModal
        open={open}
        wide
        title={mode === "create" ? "Créer un projet électrique" : "Informations générales"}
        description={
          mode === "create"
            ? "Un TGBT principal sera créé automatiquement. Aucun fichier ne sera écrit avant une sauvegarde explicite."
            : "Les informations administratives et l’association client du projet. Aucune migration destructive n’est effectuée."
        }
        onClose={onClose}
        testId="project-form-dialog"
        footer={
          <>
            <button type="button" className="button button-ghost" onClick={onClose} disabled={busy}>
              Annuler
            </button>
            <button
              type="button"
              className="button button-primary"
              disabled={busy || !form.name.trim() || !form.reference.trim()}
              onClick={() =>
                onSubmit({
                  ...form,
                  client_id: form.client_id,
                  detach_client: mode === "edit" && !form.client_id && Boolean(project?.project.client_id),
                  refresh_client: refreshClient,
                  description: form.description,
                  observations: form.observations,
                })
              }
            >
              {busy ? "Enregistrement…" : mode === "create" ? "Créer le projet" : "Appliquer"}
            </button>
          </>
        }
      >
        {error && <div className="inline-alert inline-alert-error">{error}</div>}
        <div className="form-grid form-grid-3">
          <label><span>Nom du projet *</span><input value={form.name} onChange={(event) => set("name", event.target.value)} data-testid="project-name" /></label>
          <label><span>Référence affaire *</span><input value={form.reference} onChange={(event) => set("reference", event.target.value)} data-testid="project-reference" /></label>
          {clients ? (
            <label>
              <span>Client</span>
              <select
                value={form.client_id ?? ""}
                onChange={(event) => selectClient(event.target.value)}
                data-testid="project-client-select"
              >
                <option value="">Aucun client (texte libre)</option>
                {availableClients.map((client) => (
                  <option key={client.id} value={client.id}>
                    {client.company_name}{client.is_archived ? " (archivé)" : ""}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label><span>Client</span><input value={form.client} onChange={(event) => set("client", event.target.value)} data-testid="project-client" /></label>
          )}
          <label><span>Site</span><input value={form.site} onChange={(event) => set("site", event.target.value)} data-testid="project-site" /></label>
          <label><span>Adresse du site</span><input value={form.address} onChange={(event) => set("address", event.target.value)} data-testid="project-address" /></label>
          <label><span>Auteur</span><input value={form.author} onChange={(event) => set("author", event.target.value)} data-testid="project-author" /></label>
          {clients && (
            <div className="wide-field client-summary" data-testid="project-client-summary">
              <span className="eyebrow">Coordonnées client</span>
              {selectedClient ? (
                <p>
                  <strong>{selectedClient.company_name}</strong>
                  <span>{selectedClient.address || "Adresse non renseignée"}</span>
                  <span>{selectedClient.contact_name || "Contact non renseigné"}{selectedClient.email ? ` — ${selectedClient.email}` : ""}</span>
                </p>
              ) : (
                <p className="muted-copy">Aucun client associé. Le nom saisi reste libre et n’est pas rattaché automatiquement.</p>
              )}
              <button
                type="button"
                className="button button-ghost button-small"
                onClick={() => {
                  setClientError(null);
                  setClientDialogOpen(true);
                }}
                data-testid="project-create-client"
              >
                + Créer un client
              </button>
              {selectedClient && mode === "edit" && (
                <button
                  type="button"
                  className="button button-ghost button-small"
                  onClick={() => setRefreshClient(true)}
                  disabled={refreshClient}
                  data-testid="project-refresh-client"
                  title="Recapturer les coordonnées de la fiche client"
                >
                  {refreshClient ? "Coordonnées à actualiser" : "Rafraîchir les coordonnées"}
                </button>
              )}
              {refreshClient && (
                <span className="muted-copy" data-testid="project-refresh-note">
                  Le snapshot sera actualisé à l’enregistrement.
                </span>
              )}
            </div>
          )}
          {mode === "create" && (
            <>
              <label><span>Réseau du TGBT</span><select value={form.network} onChange={(event) => set("network", event.target.value as "MONO" | "TRI")} data-testid="project-network"><option value="TRI">Triphasé</option><option value="MONO">Monophasé</option></select></label>
              <label><span>Tension composée</span><input value={form.voltage_v} onChange={(event) => set("voltage_v", event.target.value)} data-testid="project-voltage" /></label>
              <label><span>Tension simple</span><input value={form.voltage_ln_v} onChange={(event) => set("voltage_ln_v", event.target.value)} data-testid="project-voltage-ln" /></label>
              <label className="checkbox-label"><input type="checkbox" checked={form.has_neutral} onChange={(event) => set("has_neutral", event.target.checked)} /> Neutre disponible</label>
              <label><span>Révision</span><input value={form.revision} onChange={(event) => set("revision", event.target.value)} data-testid="project-revision" /></label>
            </>
          )}
        </div>
        <div className="form-grid">
          <label className="wide-field"><span>Description</span><textarea rows={3} value={form.description} onChange={(event) => set("description", event.target.value)} /></label>
          <label className="wide-field"><span>Observations</span><textarea rows={3} value={form.observations} onChange={(event) => set("observations", event.target.value)} data-testid="project-observations" /></label>
        </div>
        <p className="form-note">Les champs électriques créent le TGBT de départ. Les paramètres de la hiérarchie seront modifiables ensuite.</p>
      </FormModal>
      <ClientDialog
        open={clientDialogOpen}
        mode="create"
        busy={clientBusy}
        error={clientError}
        onSubmit={submitClient}
        onClose={() => {
          if (!clientBusy) {
            setClientDialogOpen(false);
            setClientError(null);
          }
        }}
      />
    </>
  );
}

