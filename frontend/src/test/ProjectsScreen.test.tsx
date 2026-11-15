import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { project } from "./fixtures";

vi.mock("../api", () => ({
  ApiError: class ApiError extends Error {},
  listProjectCatalog: vi.fn(async () => ({
    items: [],
    page: 1,
    page_size: 25,
    total: 0,
    total_pages: 0,
    has_next: false,
    has_previous: false,
  })),
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

const props = {
  project,
  onProjectChanged: vi.fn(),
  onNavigate: vi.fn(),
  onToast: vi.fn(),
};

describe("ProjectsScreen", () => {
  it("affiche le projet actif et ses actions", async () => {
    render(<ProjectsScreen {...props} />);
    await screen.findByText("Aucun projet ne correspond aux critères.");
    expect(screen.getByText("RECETTE-SEGYRCALC-INDUSTRIE-TERTIAIRE-01")).toBeInTheDocument();
    expect(screen.getByTestId("project-save")).toBeInTheDocument();
    expect(screen.getByTestId("project-save-as")).toBeInTheDocument();
    expect(screen.getByTestId("project-open")).toBeInTheDocument();
  });

  it("propose la création d’un projet", async () => {
    render(<ProjectsScreen {...props} project={null} />);
    await screen.findByText("Aucun projet ne correspond aux critères.");
    expect(screen.getByText("Aucun projet ouvert")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Créer un projet" }));
    expect(screen.getByTestId("project-form-dialog")).toBeInTheDocument();
  });

  it("affiche les informations générales", async () => {
    render(<ProjectsScreen {...props} />);
    await screen.findByText("Aucun projet ne correspond aux critères.");
    fireEvent.click(screen.getByRole("button", { name: /Informations/ }));
    expect(screen.getByTestId("project-form-dialog")).toBeInTheDocument();
  });
});
