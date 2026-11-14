import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ReportsScreen } from "../screens/ReportsScreen";
import { project } from "./fixtures";
import type { ReportPreview } from "../types";

vi.mock("../api", () => ({
  ApiError: class ApiError extends Error {
    status = 409;
    code = "ERREUR";
  },
  loadReportOptions: vi.fn(),
  previewReport: vi.fn(),
  exportReport: vi.fn(),
}));

vi.mock("../desktop", () => ({
  hasNativeExportDialog: vi.fn(() => false),
  chooseExportFile: vi.fn(),
  chooseExportFolder: vi.fn(),
}));

import { exportReport, loadReportOptions, previewReport } from "../api";
import { chooseExportFile, hasNativeExportDialog } from "../desktop";

const options = {
  sections: [
    { id: "cover" as const, label: "Page de garde" },
    { id: "summary" as const, label: "Synthèse générale TGBT" },
    { id: "receivers" as const, label: "Bilan des récepteurs" },
  ],
  orientations: ["portrait" as const, "landscape" as const],
  formats: ["pdf" as const, "xlsx" as const, "csv" as const],
  export_root: "C:\\CALCELECT\\development\\exports",
};

function previewFixture(): ReportPreview {
  const phases = { l1: "10", l2: "11", l3: "12" };
  return {
    snapshot: {
      snapshot_id: "8b7b0268-1111-4222-8333-944455556666",
      created_at: "2026-11-12T10:00:00Z",
      project_id: project.project.id,
      project_name: project.project.name,
      project_reference: project.project.reference,
      revision: project.state.revision,
      calculation_revision: project.state.calculation_revision,
      source_sha256: "A".repeat(64),
      config: {
        title: "Bilan de puissance — Projet test",
        sections: ["cover", "summary", "receivers"],
        orientation: "portrait",
        decimals: 2,
        units: "auto",
        csv_delimiter: ";",
        include_assumptions: true,
        include_traceability: true,
      },
      engine: project.engine,
      coherence: project.coherence,
    },
    summary: {
      project: project.project,
      totals: project.totals,
      status: project.status,
      is_calculable: project.is_calculable,
      calculated_at: project.calculated_at,
    },
    boards: [{
      reference: "TGBT-01",
      designation: "Tableau général",
      type: "TGBT",
      network: "TRI",
      voltage_v: "400",
      feeders: 2,
      receivers: 2,
      p_installed_w: "55000",
      p_after_ku_w: "48000",
      p_after_ks_w: "43240",
      q_after_ku_var: "28000",
      q_after_ks_var: "28231",
      s_after_ku_va: "56000",
      s_after_ks_va: "50168",
      neutral_current_a: "13.74",
      unbalance_percent: "11.14",
      status: "OK",
    }],
    feeders: [{
      reference: "DEP-01",
      designation: "Alimentation atelier",
      board: "TGBT-01",
      network: "TRI",
      voltage_v: "400",
      receivers: 2,
      ks: "0.9",
      p_installed_w: "20000",
      p_after_ku_w: "18000",
      p_after_ks_w: "16200",
      q_after_ku_var: "9000",
      q_after_ks_var: "8100",
      s_after_ku_va: "19000",
      s_after_ks_va: "18112",
      neutral_current_a: "4.2",
      unbalance_percent: "8.5",
      status: "OK",
    }],
    receivers: [{
      reference: "REC-01",
      designation: "Moteur atelier",
      board: "TGBT-01",
      feeder: "DEP-01",
      network: "TRI",
      voltage_v: "400",
      quantity: 1,
      installed_power_w: "15000",
      power_factor: "0.85",
      ku: "0.9",
      ks: "0.9",
      p_after_ku_w: "13500",
      p_after_ks_w: "12150",
      q_after_ku_var: "8370",
      q_after_ks_var: "7533",
      s_after_ks_va: null,
      current_a: null,
      phase: null,
      status: "OK",
      s_available: false,
      i_available: false,
    }],
    phases: {
      p: phases,
      q: phases,
      s: phases,
      i: phases,
      neutral: "13.74",
      unbalance: "11.14",
    },
    assumptions: ["Régime sinusoïdal établi."],
    diagnostics: [],
    coherence: project.coherence,
    traceability: {
      engine: project.engine,
      revision: project.state.revision,
      calculation_revision: project.state.calculation_revision,
      source_sha256: "A".repeat(64),
      calculated_at: project.calculated_at,
    },
    config: {
      title: "Bilan de puissance — Projet test",
      sections: ["cover", "summary", "receivers"],
      orientation: "portrait",
      decimals: 2,
      units: "auto",
      csv_delimiter: ";",
      include_assumptions: true,
      include_traceability: true,
    },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(hasNativeExportDialog).mockReturnValue(false);
  vi.mocked(chooseExportFile).mockResolvedValue(null);
  vi.mocked(loadReportOptions).mockResolvedValue(options);
  vi.mocked(previewReport).mockResolvedValue(previewFixture());
  vi.mocked(exportReport).mockImplementation(async (_snapshotId, format, path) => ({
    format,
    files: [{ path, bytes: 2048 }],
  }));
});

describe("ReportsScreen", () => {
  it("affiche un état vide sans projet", () => {
    render(<ReportsScreen project={null} />);
    expect(screen.getByTestId("reports-screen")).toBeInTheDocument();
    expect(screen.getByText("Aucun projet ouvert")).toBeInTheDocument();
  });

  it("génère un aperçu depuis le snapshot et affiche les valeurs moteur", async () => {
    render(<ReportsScreen project={project} />);
    await waitFor(() => expect(loadReportOptions).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId("report-preview-generate"));
    await waitFor(() => expect(previewReport).toHaveBeenCalled());
    expect(await screen.findByTestId("report-preview")).toBeInTheDocument();
    expect(screen.getByTestId("report-snapshot")).toHaveTextContent("8b7b0268-111");
    expect(screen.getAllByText("43,24 kW").length).toBeGreaterThan(0);
    expect(within(screen.getByTestId("report-table-receivers")).getAllByText("Non exposé")).toHaveLength(2);
    expect(screen.getByText(/La pagination exacte/)).toBeInTheDocument();
  });

  it("affiche les S/I individuels issus du moteur", async () => {
    const available = previewFixture();
    available.receivers[0] = {
      ...available.receivers[0],
      s_after_ks_va: "1234.56",
      current_a: "7.89",
      s_available: true,
      i_available: true,
    };
    vi.mocked(previewReport).mockResolvedValue(available);
    render(<ReportsScreen project={project} />);
    await waitFor(() => expect(loadReportOptions).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId("report-preview-generate"));
    const table = await screen.findByTestId("report-table-receivers");
    expect(within(table).getByText("1,23 kVA")).toBeInTheDocument();
    expect(within(table).getByText("7,89 A")).toBeInTheDocument();
        expect(screen.getByText(/contributions moteur après Ku et Ks/)).toBeInTheDocument();
  });

  it("configure les sections et génère un nouvel aperçu", async () => {
    render(<ReportsScreen project={project} />);
    await waitFor(() => expect(loadReportOptions).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId("report-preview-generate"));
    await waitFor(() => expect(previewReport).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByTestId("report-section-receivers"));
    fireEvent.click(screen.getByTestId("report-preview-generate"));
    await waitFor(() => expect(previewReport).toHaveBeenCalledTimes(2));
    const config = vi.mocked(previewReport).mock.calls[1][0];
    expect(config.sections).not.toContain("receivers");
  });

  it("exporte le PDF depuis le dialogue de chemin isolé", async () => {
    render(<ReportsScreen project={project} />);
    await waitFor(() => expect(loadReportOptions).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId("report-preview-generate"));
    await waitFor(() => expect(previewReport).toHaveBeenCalled());
    fireEvent.click(await screen.findByTestId("report-export-pdf"));
    expect(await screen.findByTestId("export-path-dialog")).toBeInTheDocument();
    const input = screen.getByTestId("export-path-input");
    expect((input as HTMLInputElement).value).toContain("rapport-");
    fireEvent.change(input, { target: { value: "C:\\CALCELECT\\development\\exports\\rapport-final.pdf" } });
    fireEvent.click(screen.getByTestId("export-confirm"));
    await waitFor(() => expect(exportReport).toHaveBeenCalledWith(
      "8b7b0268-1111-4222-8333-944455556666",
      "pdf",
      "C:\\CALCELECT\\development\\exports\\rapport-final.pdf",
      false,
    ));
    expect(await screen.findByTestId("report-export-result")).toBeInTheDocument();
    expect(screen.getByText(/rapport-final.pdf/)).toBeInTheDocument();
  });

  it("utilise le chemin natif Windows et confirme l'?crasement", async () => {
    vi.mocked(hasNativeExportDialog).mockReturnValue(true);
    vi.mocked(chooseExportFile).mockResolvedValue(
      "C:\\Users\\yoann\\Desktop\\Rapport 260013.pdf",
    );
    render(<ReportsScreen project={project} />);
    await waitFor(() => expect(loadReportOptions).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId("report-preview-generate"));
    await waitFor(() => expect(previewReport).toHaveBeenCalled());
    fireEvent.click(await screen.findByTestId("report-export-pdf"));
    await waitFor(() =>
      expect(exportReport).toHaveBeenCalledWith(
        "8b7b0268-1111-4222-8333-944455556666",
        "pdf",
        "C:\\Users\\yoann\\Desktop\\Rapport 260013.pdf",
        true,
      ),
    );
    expect(await screen.findByTestId("report-export-result")).toBeInTheDocument();
    expect(screen.queryByTestId("export-path-dialog")).not.toBeInTheDocument();
  });

  it("n'appelle pas le backend quand le dialogue natif est annul?", async () => {
    vi.mocked(hasNativeExportDialog).mockReturnValue(true);
    vi.mocked(chooseExportFile).mockResolvedValue(null);
    render(<ReportsScreen project={project} />);
    await waitFor(() => expect(loadReportOptions).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId("report-preview-generate"));
    await waitFor(() => expect(previewReport).toHaveBeenCalled());
    fireEvent.click(await screen.findByTestId("report-export-pdf"));
    await waitFor(() => expect(chooseExportFile).toHaveBeenCalled());
    expect(exportReport).not.toHaveBeenCalled();
    expect(screen.queryByTestId("report-export-result")).not.toBeInTheDocument();
  });

  it("désactive la génération quand le résultat est périmé", () => {
    const stale = { ...project, state: { ...project.state, stale: true, calculation_revision: 1 } };
    render(<ReportsScreen project={stale} />);
    expect(screen.getByTestId("report-stale")).toBeInTheDocument();
    expect(screen.getByTestId("report-preview-generate")).toBeDisabled();
  });
});
