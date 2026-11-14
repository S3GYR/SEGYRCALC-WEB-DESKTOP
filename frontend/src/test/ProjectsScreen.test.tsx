import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { project } from "./fixtures";

vi.mock("../api", () => ({
  ApiError: class ApiError extends Error {},
  listProjectFiles: vi.fn(async () => ({ files: [], root: "C:\\Users\\Qualification\\AppData\\Local\\SEGYR Technologies\\SEGYRCALC\\Projects" })),
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
  it("affiche le projet actif et ses actions", () => {
    render(<ProjectsScreen {...props} />);
    expect(screen.getByText("RECETTE-SEGYRCALC-INDUSTRIE-TERTIAIRE-01")).toBeInTheDocument();
    expect(screen.getByTestId("project-save")).toBeInTheDocument();
    expect(screen.getByTestId("project-save-as")).toBeInTheDocument();
    expect(screen.getByTestId("project-open")).toBeInTheDocument();
  });

  it("propose la création d’un projet", () => {
    render(<ProjectsScreen {...props} project={null} />);
    expect(screen.getByText("Aucun projet ouvert")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Créer un projet" }));
    expect(screen.getByTestId("project-form-dialog")).toBeInTheDocument();
  });

  it("affiche les informations générales", () => {
    render(<ProjectsScreen {...props} />);
    fireEvent.click(screen.getByRole("button", { name: /Informations/ }));
    expect(screen.getByTestId("project-form-dialog")).toBeInTheDocument();
  });
});
