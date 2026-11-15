import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import * as api from "../api";
import { project } from "./fixtures";
import type { ProjectCatalogItem, ProjectCatalogResponse } from "../types";

vi.mock("../api", () => ({
  ApiError: class ApiError extends Error {},
  listProjectCatalog: vi.fn(),
  openCatalogProject: vi.fn(),
  listClients: vi.fn(async () => ({ clients: [] })),
  createProject: vi.fn(),
  openProject: vi.fn(),
  saveProject: vi.fn(),
  saveProjectAs: vi.fn(),
  duplicateProject: vi.fn(),
  closeProject: vi.fn(),
  updateGeneralInfo: vi.fn(),
}));

import { ProjectsScreen } from "../screens/ProjectsScreen";

const item: ProjectCatalogItem = {
  catalog_id: "a".repeat(64),
  project_id: "project-alpha",
  name: "Projet Alpha",
  reference: "REF-ALPHA",
  client_id: "client-1",
  client_name: "Client Alpha",
  description: "Étude TGBT",
  progress: "IN_PROGRESS",
  created_at: "2026-01-01T00:00:00+00:00",
  updated_at: "2026-01-02T00:00:00+00:00",
  file_modified: "2026-01-02T00:00:00+00:00",
  format: "WEB-03",
  writable: true,
  metadata_error: null,
};

function page(overrides: Partial<ProjectCatalogResponse> = {}): ProjectCatalogResponse {
  return {
    items: [item],
    page: 1,
    page_size: 25,
    total: 1,
    total_pages: 1,
    has_next: false,
    has_previous: false,
    ...overrides,
  };
}

const props = {
  project,
  onProjectChanged: vi.fn(),
  onNavigate: vi.fn(),
  onToast: vi.fn(),
};

describe("ProjectsScreen catalogue R6.3-A", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listProjectCatalog).mockResolvedValue(page());
    vi.mocked(api.listClients).mockResolvedValue({
      clients: [
        {
          id: "client-1",
          company_name: "Client Alpha",
          address: "",
          country: "",
          contact_name: "",
          email: "",
          phone: "",
          logo: null,
          is_archived: false,
          created_at: "2026-01-01T00:00:00+00:00",
          updated_at: "2026-01-01T00:00:00+00:00",
        },
      ],
    });
    vi.mocked(api.openCatalogProject).mockResolvedValue(project);
  });

  it("affiche le catalogue, les métadonnées utiles et les contrôles accessibles", async () => {
    render(<ProjectsScreen {...props} />);
    expect(await screen.findByText("Projet Alpha")).toBeInTheDocument();
    expect(screen.getByText("REF-ALPHA · Étude TGBT")).toBeInTheDocument();
    expect(screen.getAllByText("Client Alpha").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByLabelText("Rechercher un projet")).toBeInTheDocument();
    expect(screen.getByLabelText("Filtrer par client")).toBeInTheDocument();
    expect(screen.getByLabelText("Filtrer par progression")).toBeInTheDocument();
    expect(screen.getByLabelText("Trier les projets")).toBeInTheDocument();
    expect(screen.getByLabelText("Nombre de projets par page")).toBeInTheDocument();
    expect(screen.getByText("1 projet(s)")).toBeInTheDocument();
  });

  it("réinitialise la page lors d’une recherche et transmet les filtres", async () => {
    render(<ProjectsScreen {...props} />);
    await screen.findByText("Projet Alpha");

    fireEvent.change(screen.getByTestId("project-search"), { target: { value: "alpha" } });
    await waitFor(() =>
      expect(api.listProjectCatalog).toHaveBeenLastCalledWith(
        expect.objectContaining({ q: "alpha", page: 1 }),
      ),
    );

    fireEvent.change(screen.getByTestId("project-client-filter"), { target: { value: "client-1" } });
    await waitFor(() =>
      expect(api.listProjectCatalog).toHaveBeenLastCalledWith(
        expect.objectContaining({ client_id: "client-1", page: 1 }),
      ),
    );

    fireEvent.change(screen.getByTestId("project-progress-filter"), { target: { value: "COMPLETED" } });
    await waitFor(() =>
      expect(api.listProjectCatalog).toHaveBeenLastCalledWith(
        expect.objectContaining({ progress: "COMPLETED", page: 1 }),
      ),
    );

    fireEvent.change(screen.getByTestId("project-page-size"), { target: { value: "100" } });
    await waitFor(() =>
      expect(api.listProjectCatalog).toHaveBeenLastCalledWith(
        expect.objectContaining({ page_size: 100, page: 1 }),
      ),
    );
  });

  it("navigue entre les pages sans perdre les filtres", async () => {
    vi.mocked(api.listProjectCatalog).mockImplementation(async (query) => {
      const pageNumber = query?.page ?? 1;
      return page({
        page: pageNumber,
        items: [{ ...item, catalog_id: `${pageNumber}`.repeat(64), name: `Projet page ${pageNumber}` }],
        total: 2,
        total_pages: 2,
        has_next: pageNumber < 2,
        has_previous: pageNumber > 1,
      });
    });
    render(<ProjectsScreen {...props} />);
    expect(await screen.findByText("Projet page 1")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("project-page-next"));
    expect(await screen.findByText("Projet page 2")).toBeInTheDocument();
    expect(api.listProjectCatalog).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 }));
    fireEvent.click(screen.getByTestId("project-page-previous"));
    expect(await screen.findByText("Projet page 1")).toBeInTheDocument();
  });

  it("ouvre un projet avec l’identifiant opaque du catalogue", async () => {
    render(<ProjectsScreen {...props} />);
    await screen.findByText("Projet Alpha");
    fireEvent.click(screen.getByTestId(`open-project-${item.catalog_id}`));
    await waitFor(() => expect(api.openCatalogProject).toHaveBeenCalledWith(item.catalog_id));
    await waitFor(() => expect(props.onNavigate).toHaveBeenCalledWith("balance"));
  });

  it("affiche un état vide et un message d’erreur explicite", async () => {
    vi.mocked(api.listProjectCatalog).mockResolvedValue(page({ items: [], total: 0, total_pages: 0 }));
    const { unmount } = render(<ProjectsScreen {...props} />);
    expect(await screen.findByText("Aucun projet ne correspond aux critères.")).toBeInTheDocument();
    unmount();

    vi.mocked(api.listProjectCatalog).mockRejectedValue(new Error("Catalogue inaccessible"));
    render(<ProjectsScreen {...props} />);
    expect(await screen.findByText("Catalogue inaccessible")).toBeInTheDocument();
  });
});
