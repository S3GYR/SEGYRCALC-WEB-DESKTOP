import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import * as api from "../api";
import { project } from "./fixtures";

vi.mock("../api", () => ({
  ApiError: class ApiError extends Error {},
  loadCurrentProject: vi.fn(async () => project),
  saveProject: vi.fn(async () => project),
  updateLoad: vi.fn(async () => project),
  updateFeeder: vi.fn(async () => project),
  undoProject: vi.fn(async () => project),
  redoProject: vi.fn(async () => project),
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
  getCompany: vi.fn(async () => ({
    configured: false,
    company: {
      legal_name: "",
      trade_name: "",
      address_line1: "",
      address_line2: "",
      postal_code: "",
      city: "",
      country: "",
      phone: "",
      email: "",
      website: "",
      siren: "",
      siret: "",
      vat_number: "",
      manager_name: "",
      manager_role: "",
      document_footer: "",
      logo: null,
    },
  })),
  updateCompany: vi.fn(),
  uploadCompanyLogo: vi.fn(),
  deleteCompanyLogo: vi.fn(),
  fetchCompanyLogo: vi.fn(async () => null),
  createProject: vi.fn(async () => project),
  openProject: vi.fn(async () => project),
  saveProjectAs: vi.fn(async () => project),
  duplicateProject: vi.fn(async () => project),
  closeProject: vi.fn(async () => ({ closed: true })),
  updateGeneralInfo: vi.fn(async () => project),
  loadReportOptions: vi.fn(async () => ({
    sections: [
      { id: "cover", label: "Page de garde" },
      { id: "general", label: "Informations générales" },
      { id: "summary", label: "Synthèse générale TGBT" },
      { id: "architecture", label: "Architecture électrique" },
      { id: "boards", label: "Synthèses des tableaux" },
      { id: "feeders", label: "Bilan des départs" },
      { id: "receivers", label: "Bilan des récepteurs" },
      { id: "coefficients", label: "Coefficients Ku et Ks" },
      { id: "phases", label: "Répartition des phases" },
      { id: "assumptions", label: "Hypothèses et limites" },
      { id: "traceability", label: "Traçabilité" },
    ],
    orientations: ["portrait", "landscape"],
    formats: ["pdf", "xlsx", "csv"],
    export_root: "C:\\CALCELECT\\development\\exports",
  })),
  previewReport: vi.fn(),
  exportReport: vi.fn(),
}));

import App from "../App";

describe("Application SEGYRCALC", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/");
  });

  it("charge le projet et navigue entre les modules", async () => {
    render(<App />);
    expect(await screen.findByText("Bonjour, votre espace de travail est prêt.")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("nav-projects"));
    expect(await screen.findByText("Créez, ouvrez et enregistrez vos projets.")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("nav-architecture"));
    expect(await screen.findByText("Du TGBT au récepteur.")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("nav-settings"));
    expect(await screen.findByText("Environnement BETA")).toBeInTheDocument();
  });

  it("déclenche Annuler avec Ctrl+Z hors champ de saisie", async () => {
    render(<App />);
    await screen.findByText("Bonjour, votre espace de travail est prêt.");
    fireEvent.keyDown(window, { key: "z", ctrlKey: true });
    await waitFor(() => expect(api.undoProject).toHaveBeenCalledWith(project.state.revision));
  });

  it("ouvre les modules bibliothèque et rapports avec un statut explicite", async () => {
    render(<App />);
    await screen.findByText("Bonjour, votre espace de travail est prêt.");
    fireEvent.click(screen.getByTestId("nav-library"));
    expect(await screen.findByText("Module prévu pour une mission ultérieure")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("nav-reports"));
    expect(await screen.findByText("Synthèses et exports techniques")).toBeInTheDocument();
    expect(await screen.findByText("Aperçu non généré")).toBeInTheDocument();
  });
});
