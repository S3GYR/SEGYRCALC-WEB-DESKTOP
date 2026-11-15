import { diag } from "./diagnostics";
import type {
  Client,
  CompanyPayload,
  CompanyProfile,
  DeletionPreview,
  PowerPayload,
  PowerRequest,
  ProjectCatalogQuery,
  ProjectCatalogResponse,
  ProjectFileList,
  ProjectPayload,
  SourcePayload,
  ReportConfig,
  ReportExportResult,
  ReportOptions,
  ReportPreview,
} from "./types";

const token = document
  .querySelector<HTMLMetaElement>('meta[name="segyr-session-token"]')
  ?.content.trim();

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status: number, code = "ERREUR_LOCALE") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!token || token === "__SEGYR_SESSION_TOKEN__") {
    throw new ApiError("Jeton de session local absent.", 0);
  }
  const started = typeof performance !== "undefined" ? performance.now() : 0;
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-SEGYR-Token": token,
        ...(init?.headers ?? {}),
      },
    });
  } catch (error) {
    diag("api_fetch_error", {
      path,
      message: String((error as { message?: string } | undefined)?.message ?? error ?? ""),
    });
    throw error;
  }
  diag("api_response", {
    path,
    status: response.status,
    duration_ms: Math.round(((typeof performance !== "undefined" ? performance.now() : 0) - started) * 10) / 10,
  });
  if (!response.ok) {
    let detail = `Erreur locale ${response.status}`;
    let code = "ERREUR_LOCALE";
    try {
      const payload = (await response.json()) as { detail?: string; code?: string };
      if (payload.detail) detail = payload.detail;
      if (payload.code) code = payload.code;
    } catch {
      // Keep the status-based message when the body is not JSON.
    }
    throw new ApiError(detail, response.status, code);
  }
  return (await response.json()) as T;
}

export async function loadCurrentProject(): Promise<ProjectPayload | null> {
  try {
    return await request<ProjectPayload>("/api/project");
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function loadEngineFixture(): Promise<ProjectPayload> {
  return request<ProjectPayload>("/api/engine/project");
}

export function loadEngineInfo(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>("/api/engine/info");
}

export function calculatePower(payload: PowerRequest): Promise<PowerPayload> {
  return request<PowerPayload>("/api/engine/power", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createProject(payload: Record<string, unknown>): Promise<ProjectPayload> {
  return request<ProjectPayload>("/api/project/new", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function openProject(path: string): Promise<ProjectPayload> {
  return request<ProjectPayload>("/api/project/open", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}

export function saveProject(path: string | null = null, overwrite = false): Promise<ProjectPayload> {
  return request<ProjectPayload>("/api/project/save", {
    method: "POST",
    body: JSON.stringify({ path, overwrite }),
  });
}

export function saveProjectAs(path: string, overwrite = false): Promise<ProjectPayload> {
  return request<ProjectPayload>("/api/project/save-as", {
    method: "POST",
    body: JSON.stringify({ path, overwrite }),
  });
}

export function duplicateProject(path: string, overwrite = false): Promise<ProjectPayload> {
  return request<ProjectPayload>("/api/project/duplicate", {
    method: "POST",
    body: JSON.stringify({ path, overwrite }),
  });
}

export function closeProject(): Promise<{ closed: boolean }> {
  return request<{ closed: boolean }>("/api/project/close", { method: "POST" });
}

export function listClients(search = "", includeArchived = true): Promise<{ clients: Client[] }> {
  const params = new URLSearchParams();
  if (search.trim()) params.set("search", search.trim());
  params.set("include_archived", includeArchived ? "true" : "false");
  return request<{ clients: Client[] }>(`/api/clients?${params.toString()}`);
}

export function getClient(id: string): Promise<Client> {
  return request<Client>(`/api/clients/${encodeURIComponent(id)}`);
}

export function createClient(payload: Record<string, unknown>): Promise<Client> {
  return request<Client>("/api/clients", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateClient(id: string, payload: Record<string, unknown>): Promise<Client> {
  return request<Client>(`/api/clients/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function archiveClient(id: string): Promise<Client> {
  return request<Client>(`/api/clients/${encodeURIComponent(id)}/archive`, { method: "POST" });
}

export function reactivateClient(id: string): Promise<Client> {
  return request<Client>(`/api/clients/${encodeURIComponent(id)}/reactivate`, { method: "POST" });
}

export function getCompany(): Promise<CompanyPayload> {
  return request<CompanyPayload>("/api/company");
}

export function updateCompany(payload: CompanyProfile): Promise<CompanyPayload> {
  return request<CompanyPayload>("/api/company", { method: "PUT", body: JSON.stringify(payload) });
}

export function updateProjectSource(
  source: SourcePayload | null,
  expectedRevision: number,
): Promise<ProjectPayload> {
  return request<ProjectPayload>("/api/project/source", {
    method: "PUT",
    body: JSON.stringify({ expected_revision: expectedRevision, source }),
  });
}

export function deleteProjectSource(expectedRevision: number): Promise<ProjectPayload> {
  return request<ProjectPayload>(
    `/api/project/source?expected_revision=${encodeURIComponent(String(expectedRevision))}`,
    { method: "DELETE" },
  );
}

export async function uploadCompanyLogo(file: File): Promise<CompanyPayload> {
  if (!token || token === "__SEGYR_SESSION_TOKEN__") {
    throw new ApiError("Jeton de session local absent.", 0);
  }
  const response = await fetch("/api/company/logo", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": file.type || "application/octet-stream",
      "X-SEGYR-Token": token,
    },
    body: file,
  });
  if (!response.ok) {
    let detail = `Erreur locale ${response.status}`;
    let code = "ERREUR_LOCALE";
    try {
      const payload = (await response.json()) as { detail?: string; code?: string };
      if (payload.detail) detail = payload.detail;
      if (payload.code) code = payload.code;
    } catch {
      // Keep the status-based message when the body is not JSON.
    }
    throw new ApiError(detail, response.status, code);
  }
  return (await response.json()) as CompanyPayload;
}

export function deleteCompanyLogo(): Promise<CompanyPayload> {
  return request<CompanyPayload>("/api/company/logo", { method: "DELETE" });
}

export async function fetchCompanyLogo(): Promise<string | null> {
  if (!token || token === "__SEGYR_SESSION_TOKEN__") return null;
  const response = await fetch("/api/company/logo", {
    credentials: "same-origin",
    headers: { "X-SEGYR-Token": token },
  });
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new ApiError(`Logo entreprise indisponible (${response.status}).`, response.status, "COMPANY_LOGO_ABSENT");
  }
  return URL.createObjectURL(await response.blob());
}

export async function uploadClientLogo(id: string, file: File): Promise<Client> {
  if (!token || token === "__SEGYR_SESSION_TOKEN__") {
    throw new ApiError("Jeton de session local absent.", 0);
  }
  const response = await fetch(`/api/clients/${encodeURIComponent(id)}/logo`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": file.type || "application/octet-stream",
      "X-SEGYR-Token": token,
    },
    body: file,
  });
  if (!response.ok) {
    let detail = `Erreur locale ${response.status}`;
    let code = "ERREUR_LOCALE";
    try {
      const payload = (await response.json()) as { detail?: string; code?: string };
      if (payload.detail) detail = payload.detail;
      if (payload.code) code = payload.code;
    } catch {
      // Keep the status-based message when the body is not JSON.
    }
    throw new ApiError(detail, response.status, code);
  }
  return (await response.json()) as Client;
}

export async function deleteClientLogo(id: string): Promise<Client> {
  return request<Client>(`/api/clients/${encodeURIComponent(id)}/logo`, { method: "DELETE" });
}

export async function fetchClientLogo(id: string): Promise<string | null> {
  if (!token || token === "__SEGYR_SESSION_TOKEN__") return null;
  const response = await fetch(`/api/clients/${encodeURIComponent(id)}/logo`, {
    credentials: "same-origin",
    headers: { "X-SEGYR-Token": token },
  });
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new ApiError(`Logo client indisponible (${response.status}).`, response.status, "CLIENT_LOGO_ABSENT");
  }
  return URL.createObjectURL(await response.blob());
}

function withRevision(payload: Record<string, unknown>, expectedRevision: number): Record<string, unknown> {
  return { ...payload, expected_revision: expectedRevision };
}

export function updateGeneralInfo(
  payload: Record<string, unknown>,
  expectedRevision: number,
): Promise<ProjectPayload> {
  return request<ProjectPayload>("/api/project/general", {
    method: "POST",
    body: JSON.stringify(withRevision(payload, expectedRevision)),
  });
}

export function listProjectFiles(): Promise<ProjectFileList> {
  return request<ProjectFileList>("/api/project/files");
}

export function listProjectCatalog(query: ProjectCatalogQuery = {}): Promise<ProjectCatalogResponse> {
  const params = new URLSearchParams();
  if (query.q?.trim()) params.set("q", query.q.trim());
  if (query.client_id) params.set("client_id", query.client_id);
  if (query.progress) params.set("progress", query.progress);
  if (query.date_field) params.set("date_field", query.date_field);
  if (query.date_from) params.set("date_from", query.date_from);
  if (query.date_to) params.set("date_to", query.date_to);
  if (query.sort) params.set("sort", query.sort);
  if (query.page) params.set("page", String(query.page));
  if (query.page_size) params.set("page_size", String(query.page_size));
  const suffix = params.toString();
  return request<ProjectCatalogResponse>(`/api/projects${suffix ? `?${suffix}` : ""}`);
}

export function openCatalogProject(catalogId: string): Promise<ProjectPayload> {
  return request<ProjectPayload>(`/api/projects/${encodeURIComponent(catalogId)}/open`, {
    method: "POST",
  });
}

export function addBoard(payload: Record<string, unknown>, expectedRevision: number): Promise<ProjectPayload> {
  return request<ProjectPayload>("/api/project/boards", {
    method: "POST",
    body: JSON.stringify(withRevision(payload, expectedRevision)),
  });
}

export function updateBoard(
  id: string,
  payload: Record<string, unknown>,
  expectedRevision: number,
): Promise<ProjectPayload> {
  return request<ProjectPayload>(`/api/project/boards/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(withRevision(payload, expectedRevision)),
  });
}

export function moveBoard(
  id: string,
  destinationBoardId: string,
  expectedRevision: number,
): Promise<ProjectPayload> {
  return request<ProjectPayload>(`/api/project/boards/${encodeURIComponent(id)}/move`, {
    method: "POST",
    body: JSON.stringify(withRevision({ destination_board_id: destinationBoardId }, expectedRevision)),
  });
}

export function duplicateBoard(
  id: string,
  destinationBoardId: string | null,
  expectedRevision: number,
): Promise<ProjectPayload> {
  return request<ProjectPayload>(`/api/project/boards/${encodeURIComponent(id)}/duplicate`, {
    method: "POST",
    body: JSON.stringify(withRevision({ destination_board_id: destinationBoardId }, expectedRevision)),
  });
}

export function deleteBoard(
  id: string,
  expectedRevision: number,
  cascade = false,
): Promise<ProjectPayload> {
  return request<ProjectPayload>(
    `/api/project/boards/${encodeURIComponent(id)}?expected_revision=${expectedRevision}&cascade=${cascade}`,
    { method: "DELETE" },
  );
}

export function addFeeder(payload: Record<string, unknown>, expectedRevision: number): Promise<ProjectPayload> {
  return request<ProjectPayload>("/api/project/feeders", {
    method: "POST",
    body: JSON.stringify(withRevision(payload, expectedRevision)),
  });
}

export function addFeederWithLoad(payload: Record<string, unknown>, expectedRevision: number): Promise<ProjectPayload> {
  return request<ProjectPayload>("/api/project/feeders-with-load", {
    method: "POST",
    body: JSON.stringify(withRevision(payload, expectedRevision)),
  });
}

export function updateFeeder(
  id: string,
  payload: Record<string, unknown>,
  expectedRevision: number,
): Promise<ProjectPayload> {
  return request<ProjectPayload>(`/api/project/feeders/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(withRevision(payload, expectedRevision)),
  });
}

export function moveFeeder(
  id: string,
  destinationBoardId: string,
  expectedRevision: number,
): Promise<ProjectPayload> {
  return request<ProjectPayload>(`/api/project/feeders/${encodeURIComponent(id)}/move`, {
    method: "POST",
    body: JSON.stringify(withRevision({ destination_board_id: destinationBoardId }, expectedRevision)),
  });
}

export function duplicateFeeder(
  id: string,
  destinationBoardId: string | null,
  expectedRevision: number,
): Promise<ProjectPayload> {
  return request<ProjectPayload>(`/api/project/feeders/${encodeURIComponent(id)}/duplicate`, {
    method: "POST",
    body: JSON.stringify(withRevision({ destination_board_id: destinationBoardId }, expectedRevision)),
  });
}

export function deleteFeeder(
  id: string,
  expectedRevision: number,
  cascade = false,
): Promise<ProjectPayload> {
  return request<ProjectPayload>(
    `/api/project/feeders/${encodeURIComponent(id)}?expected_revision=${expectedRevision}&cascade=${cascade}`,
    { method: "DELETE" },
  );
}

export function addLoad(payload: Record<string, unknown>, expectedRevision: number): Promise<ProjectPayload> {
  return request<ProjectPayload>("/api/project/loads", {
    method: "POST",
    body: JSON.stringify(withRevision(payload, expectedRevision)),
  });
}

export function updateLoad(
  id: string,
  payload: Record<string, unknown>,
  expectedRevision: number,
): Promise<ProjectPayload> {
  return request<ProjectPayload>(`/api/project/loads/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(withRevision(payload, expectedRevision)),
  });
}

export function moveLoad(
  id: string,
  destinationFeederId: string,
  expectedRevision: number,
): Promise<ProjectPayload> {
  return request<ProjectPayload>(`/api/project/loads/${encodeURIComponent(id)}/move`, {
    method: "POST",
    body: JSON.stringify(withRevision({ destination_feeder_id: destinationFeederId }, expectedRevision)),
  });
}

export function duplicateLoad(
  id: string,
  destinationFeederId: string | null,
  expectedRevision: number,
): Promise<ProjectPayload> {
  return request<ProjectPayload>(`/api/project/loads/${encodeURIComponent(id)}/duplicate`, {
    method: "POST",
    body: JSON.stringify(withRevision({ destination_feeder_id: destinationFeederId }, expectedRevision)),
  });
}

export function deleteLoad(
  id: string,
  expectedRevision: number,
  cascade = false,
): Promise<ProjectPayload> {
  return request<ProjectPayload>(
    `/api/project/loads/${encodeURIComponent(id)}?expected_revision=${expectedRevision}&cascade=${cascade}`,
    { method: "DELETE" },
  );
}

export function deletionPreview(kind: "board" | "feeder" | "load", id: string): Promise<DeletionPreview> {
  return request<DeletionPreview>(`/api/project/deletion-preview/${kind}/${encodeURIComponent(id)}`);
}

export function undoProject(expectedRevision: number): Promise<ProjectPayload> {
  return request<ProjectPayload>("/api/project/undo", {
    method: "POST",
    body: JSON.stringify({ expected_revision: expectedRevision }),
  });
}

export function redoProject(expectedRevision: number): Promise<ProjectPayload> {
  return request<ProjectPayload>("/api/project/redo", {
    method: "POST",
    body: JSON.stringify({ expected_revision: expectedRevision }),
  });
}

export function recalculateProject(): Promise<ProjectPayload> {
  return request<ProjectPayload>("/api/project/recalculate", { method: "POST" });
}

export function loadReportOptions(): Promise<ReportOptions> {
  return request<ReportOptions>("/api/reports/options");
}

export function previewReport(config: ReportConfig): Promise<ReportPreview> {
  return request<ReportPreview>("/api/reports/preview", {
    method: "POST",
    body: JSON.stringify({ config }),
  });
}

export function exportReport(
  snapshotId: string,
  format: "pdf" | "xlsx" | "csv",
  path: string,
  overwrite: boolean,
): Promise<ReportExportResult> {
  return request<ReportExportResult>("/api/reports/export", {
    method: "POST",
    body: JSON.stringify({ snapshot_id: snapshotId, format, path, overwrite }),
  });
}

export function listReportExports(): Promise<{ root: string; files: Array<Record<string, unknown>> }> {
  return request<{ root: string; files: Array<Record<string, unknown>> }>("/api/reports/exports");
}
