import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("../api", () => ({
  loadProject: vi.fn(),
  calculatePower: vi.fn(async () => ({
    status: "OK",
    mode: "P_KNOWN",
    network: "TRI",
    power_nature: "ABSORBED",
    p_abs_w: "8000",
    p_useful_w: null,
    s_va: "10000",
    q_var: "6000",
    current_a: "14.433756729740644112",
    voltage_v: "400",
    power_factor: "0.8",
    efficiency: null,
    diagnostics: [],
    engine: {
      source: "read-only",
      function: "segyr_calc.core.power.calculate_power",
      source_sha256: "A".repeat(64),
    },
  })),
  loadEngineInfo: vi.fn(),
}));

import { EngineScreen } from "../screens/EngineScreen";
import { calculatePower } from "../api";

describe("EngineScreen", () => {
  it("appelle le moteur et affiche les résultats", async () => {
    render(<EngineScreen />);
    fireEvent.click(screen.getByTestId("engine-run"));
    expect(await screen.findByText("14,43 A")).toBeInTheDocument();
    expect(screen.getByText("8,00 kW")).toBeInTheDocument();
    expect(screen.getByText("6,00 kvar")).toBeInTheDocument();
    expect(screen.getByTestId("engine-result")).toBeInTheDocument();
  });

  it("propose une entrée invalide sans planter l’interface", async () => {
    render(<EngineScreen />);
    fireEvent.click(screen.getByTestId("engine-run-error"));
    await waitFor(() => expect(screen.getByTestId("engine-result")).toBeInTheDocument());
  });

  it("affiche une erreur locale sans fuite technique", async () => {
    vi.mocked(calculatePower).mockRejectedValueOnce(new Error("service local indisponible"));
    render(<EngineScreen />);
    fireEvent.click(screen.getByTestId("engine-run"));
    expect(await screen.findByText("Appel local impossible")).toBeInTheDocument();
    expect(screen.getByText("service local indisponible")).toBeInTheDocument();
  });
});
