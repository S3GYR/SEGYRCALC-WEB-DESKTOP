import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  updateProjectSource: vi.fn(),
  deleteProjectSource: vi.fn(),
}));

vi.mock("../api", () => ({
  ApiError: class ApiError extends Error {},
  ...mocks,
}));

import { SourcePanel } from "../components/SourcePanel";
import { project as fixture } from "./fixtures";
import type { ProjectPayload, SourcePayload } from "../types";

const source: SourcePayload = {
  id: "11111111-1111-4111-8111-111111111111",
  source_type: "AC_THREE_PHASE",
  reference: "SRC-01",
  designation: "Source principale",
  quantity: 1,
  phase_system: "TRI",
  rated_power: "250",
  rated_power_unit: "KVA",
  nominal_voltage: "400",
  voltage_unit: "V",
  frequency_hz: "50",
  power_factor: "0.8",
  primary_voltage: null,
  primary_voltage_unit: "V",
  secondary_voltage: null,
  secondary_voltage_unit: "V",
  short_circuit_voltage_percent: null,
  coupling: "",
  operating_mode: "SINGLE",
  active_power: null,
  active_power_unit: "W",
  capacity_ah: null,
  max_current_a: null,
  max_power_w: null,
  technology: "",
  connection_type: "",
  subscribed_power_kva: null,
  connection_power_kva: null,
};

function projectWith(sourceValue: SourcePayload | null): ProjectPayload {
  return { ...fixture, source: sourceValue } as ProjectPayload;
}

describe("SourcePanel — S2", () => {
  it("affiche l'absence de source sans en créer", () => {
    const onChanged = vi.fn();
    render(<SourcePanel project={projectWith(null)} onProjectChanged={onChanged} onToast={vi.fn()} />);
    expect(screen.getByText(/Aucune source électrique configurée/)).toBeInTheDocument();
    expect(screen.getByTestId("source-edit")).toHaveTextContent("Configurer une source");
    expect(onChanged).not.toHaveBeenCalled();
  });

  it("crée une source AC triphasée et notifie le projet", async () => {
    const onChanged = vi.fn();
    const updated = projectWith(source);
    mocks.updateProjectSource.mockResolvedValue(updated);
    render(<SourcePanel project={projectWith(null)} onProjectChanged={onChanged} onToast={vi.fn()} />);
    fireEvent.click(screen.getByTestId("source-edit"));
    fireEvent.change(screen.getByTestId("source-reference"), { target: { value: "SRC-01" } });
    fireEvent.change(screen.getByTestId("source-designation"), { target: { value: "Source principale" } });
    fireEvent.change(screen.getByTestId("source-power"), { target: { value: "250" } });
    fireEvent.change(screen.getByTestId("source-voltage"), { target: { value: "400" } });
    fireEvent.change(screen.getByTestId("source-frequency"), { target: { value: "50" } });
    fireEvent.change(screen.getByTestId("source-power-factor"), { target: { value: "0.8" } });
    fireEvent.click(screen.getByTestId("source-save"));
    await waitFor(() => expect(mocks.updateProjectSource).toHaveBeenCalled());
    const [payload, revision] = mocks.updateProjectSource.mock.calls[0];
    expect(payload).toEqual(expect.objectContaining({
      source_type: "AC_THREE_PHASE",
      reference: "SRC-01",
      designation: "Source principale",
      rated_power: "250",
      nominal_voltage: "400",
      frequency_hz: "50",
      power_factor: "0.8",
    }));
    expect(revision).toBe(fixture.state.revision);
    expect(onChanged).toHaveBeenCalledWith(updated);
  });

  it("affiche une source existante et propose la suppression", () => {
    render(<SourcePanel project={projectWith(source)} onProjectChanged={vi.fn()} onToast={vi.fn()} />);
    expect(screen.getByText("Source AC triphasée")).toBeInTheDocument();
    expect(screen.getByText("SRC-01 · Source principale")).toBeInTheDocument();
    expect(screen.getByTestId("source-delete")).toBeInTheDocument();
  });
});
