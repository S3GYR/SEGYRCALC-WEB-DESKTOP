import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  archiveClient,
  createClient,
  deleteClientLogo,
  listClients,
  reactivateClient,
  updateClient,
  uploadClientLogo,
} from "../api";
import { ClientDialog } from "../components/ClientDialog";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { DataTable, type DataColumn } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { PageHeader } from "../components/PageHeader";
import { SearchInput } from "../components/SearchInput";
import { Toolbar } from "../components/Toolbar";
import { shortDate } from "../format";
import { Icon } from "../icons";
import type { Client } from "../types";

function errorText(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : error instanceof Error
      ? error.message
      : "Opération client impossible.";
}

export function ClientsScreen({ onToast }: { onToast: (message: string, tone: "info" | "success" | "warning" | "error") => void }) {
  const [clients, setClients] = useState<Client[]>([]);
  const [search, setSearch] = useState("");
  const [includeArchived, setIncludeArchived] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Client | null>(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [archiveTarget, setArchiveTarget] = useState<Client | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listClients("", true);
      setClients(result.clients);
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const filtered = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return clients.filter((client) => {
      if (!includeArchived && client.is_archived) return false;
      if (!query) return true;
      return [
        client.company_name,
        client.contact_name,
        client.email,
        client.phone,
        client.address,
        client.address_line1,
        client.address_line2,
        client.postal_code,
        client.city,
        client.formatted_address,
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase()
        .includes(query);
    });
  }, [clients, includeArchived, search]);

  const submit = async (
    payload: Record<string, unknown>,
    logoFile: File | null,
    removeLogo: boolean,
  ) => {
    setBusy(true);
    setFormError(null);
    try {
      let client = editing
        ? await updateClient(editing.id, payload)
        : await createClient(payload);
      if (logoFile) {
        client = await uploadClientLogo(client.id, logoFile);
      } else if (removeLogo && client.logo) {
        client = await deleteClientLogo(client.id);
      }
      setClients((current) => {
        const next = editing
          ? current.map((item) => (item.id === client.id ? client : item))
          : [...current, client];
        return next.sort((a, b) => a.company_name.localeCompare(b.company_name));
      });
      setDialogOpen(false);
      setEditing(null);
      onToast(editing ? "Client modifié." : "Client créé.", "success");
    } catch (caught) {
      const message = errorText(caught);
      setFormError(message);
      onToast(message, "error");
    } finally {
      setBusy(false);
    }
  };

  const confirmArchive = () => {
    if (!archiveTarget) return;
    setBusy(true);
    void archiveClient(archiveTarget.id)
      .then((client) => {
        setClients((current) => current.map((item) => (item.id === client.id ? client : item)));
        setArchiveTarget(null);
        onToast("Client archivé. Les projets associés conservent leur snapshot.", "success");
      })
      .catch((caught) => onToast(errorText(caught), "error"))
      .finally(() => setBusy(false));
  };

  const reactivate = (client: Client) => {
    setBusy(true);
    void reactivateClient(client.id)
      .then((updated) => {
        setClients((current) => current.map((item) => (item.id === updated.id ? updated : item)));
        onToast("Client réactivé.", "success");
      })
      .catch((caught) => onToast(errorText(caught), "error"))
      .finally(() => setBusy(false));
  };

  const columns: DataColumn<Client>[] = [
    {
      key: "company_name",
      label: "Raison sociale",
      width: 220,
      sortable: true,
      render: (client) => (
        <span className="cell-main">
          {client.company_name}
          {client.is_archived && <span className="mini-badge">Archivé</span>}
        </span>
      ),
    },
    { key: "contact_name", label: "Contact", width: 150, render: (client) => client.contact_name || "—" },
    { key: "email", label: "E-mail", width: 210, render: (client) => client.email || "—" },
    { key: "phone", label: "Téléphone", width: 150, render: (client) => client.phone || "—" },
    { key: "updated_at", label: "Modifié", width: 130, render: (client) => shortDate(client.updated_at) },
    {
      key: "actions",
      label: "Actions",
      width: 190,
      render: (client) => (
        <div className="row-actions">
          <button
            type="button"
            className="button button-ghost button-small"
            onClick={() => {
              setEditing(client);
              setFormError(null);
              setDialogOpen(true);
            }}
            data-testid={`client-edit-${client.id}`}
          >
            <Icon name="edit" size={13} /> Modifier
          </button>
          {client.is_archived ? (
            <button
              type="button"
              className="button button-ghost button-small"
              onClick={() => reactivate(client)}
              disabled={busy}
              data-testid={`client-reactivate-${client.id}`}
            >
              Réactiver
            </button>
          ) : (
            <button
              type="button"
              className="button button-ghost button-small"
              onClick={() => setArchiveTarget(client)}
              disabled={busy}
              data-testid={`client-archive-${client.id}`}
            >
              Archiver
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="page-stack" data-testid="clients-screen">
      <PageHeader
        eyebrow="Référentiel local — WEB-08"
        title="Clients."
        description="Les coordonnées client sont conservées localement. Les projets associés gardent un snapshot figé, actualisable explicitement."
        badge={<span className="outline-badge">{clients.length} clients</span>}
        actions={
          <button
            type="button"
            className="button button-primary button-small"
            onClick={() => {
              setEditing(null);
              setFormError(null);
              setDialogOpen(true);
            }}
            data-testid="client-new"
          >
            <Icon name="projects" size={14} /> Nouveau client
          </button>
        }
      />
      <Toolbar
        left={
          <SearchInput
            label="Rechercher un client"
            value={search}
            onChange={setSearch}
            placeholder="Raison sociale, contact, e-mail, téléphone…"
            testId="client-search"
          />
        }
        right={
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={(event) => setIncludeArchived(event.target.checked)}
              data-testid="client-include-archived"
            />{" "}
            Afficher les archivés
          </label>
        }
      />
      {error ? (
        <ErrorState title="Référentiel client indisponible" message={error} onRetry={() => void load()} />
      ) : loading ? (
        <div className="panel loading-panel">Chargement des clients…</div>
      ) : filtered.length === 0 ? (
        <EmptyState
          title={clients.length === 0 ? "Aucun client" : "Aucun résultat"}
          description={
            clients.length === 0
              ? "Créez la première fiche client pour l’associer à un projet."
              : "Modifiez la recherche ou affichez les archivés."
          }
        />
      ) : (
        <section className="panel">
          <DataTable
            columns={columns}
            rows={filtered}
            rowKey={(client) => client.id}
            emptyMessage="Aucun client."
            testId="clients-table"
            rowTestId={(client) => `client-row-${client.id}`}
            ariaLabel="Liste des clients"
          />
        </section>
      )}
      <ClientDialog
        open={dialogOpen}
        mode={editing ? "edit" : "create"}
        initial={editing}
        busy={busy}
        error={formError}
        onSubmit={submit}
        onClose={() => {
          if (busy) return;
          setDialogOpen(false);
          setEditing(null);
          setFormError(null);
        }}
      />
      <ConfirmDialog
        open={archiveTarget !== null}
        title="Archiver ce client ?"
        message={
          archiveTarget
            ? `La fiche « ${archiveTarget.company_name} » sera archivée. Les projets associés conservent leur snapshot et restent lisibles.`
            : ""
        }
        confirmLabel="Archiver"
        danger
        onConfirm={confirmArchive}
        onCancel={() => setArchiveTarget(null)}
      />
    </div>
  );
}

