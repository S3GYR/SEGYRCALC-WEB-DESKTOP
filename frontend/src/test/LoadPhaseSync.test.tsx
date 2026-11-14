import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { EntityDialog } from "../components/EntityDialog";
import { feeder, load, project } from "./fixtures";
import type { FeederSummary, LoadSummary, ProjectPayload } from "../types";

const monoFeeder: FeederSummary = {
  ...feeder,
  id: "DEP-MONO",
  designation: "Départ éclairage",
  network: "MONO",
  voltage_v: "230",
  phase_voltage_v: "230",
  voltage_ln_v: "230",
  has_neutral: true,
  phase: "L2",
  distribution_type: "MONO_N",
};

const monoProject: ProjectPayload = {
  ...project,
  feeders: [monoFeeder],
  loads: [{ ...load, feeder_id: monoFeeder.id, network: "MONO", voltage_v: "230", phase: "L2" }],
};

const noNeutralFeeder: FeederSummary = {
  ...feeder,
  id: "DEP-TRI-SANS-N",
  network: "TRI",
  has_neutral: false,
  phase: null,
  distribution_type: "TRI_NO_N",
};

const noNeutralProject: ProjectPayload = {
  ...project,
  feeders: [noNeutralFeeder],
  loads: [],
};

describe("EntityDialog — synchronisation des phases", () => {
  it("hérite la phase et la tension du départ MONO_N à la création", () => {
    const onSubmit = vi.fn();
    render(
      <EntityDialog
        open
        kind="load"
        mode="create"
        project={monoProject}
        initial={null}
        busy={false}
        error={null}
        onSubmit={onSubmit}
        onClose={() => undefined}
      />,
    );
    expect(screen.getByTestId("entity-phase")).toHaveValue("L2");
    expect(screen.getByTestId("entity-phase")).toHaveAttribute("readonly");
    expect(screen.getByTestId("entity-voltage")).toHaveValue("230");
    expect(screen.getByTestId("entity-voltage")).toHaveAttribute("readonly");
    expect((screen.getByTestId("entity-network") as HTMLInputElement).value).toContain("Monophas");
    fireEvent.change(screen.getByTestId("entity-designation"), { target: { value: "REC-MONO" } });
    fireEvent.click(screen.getByRole("button", { name: "Valider" }));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        network: "MONO",
        phase: "L2",
        voltage_v: "230",
      }),
    );
  });

  it("autorise la modification de phase depuis le récepteur en mode édition", () => {
    const onSubmit = vi.fn();
    const initial = monoProject.loads[0] as LoadSummary;
    render(
      <EntityDialog
        open
        kind="load"
        mode="edit"
        project={monoProject}
        initial={initial}
        busy={false}
        error={null}
        onSubmit={onSubmit}
        onClose={() => undefined}
      />,
    );
    expect(screen.getByTestId("load-phase-sync-note")).toBeInTheDocument();
    expect(screen.getByTestId("entity-phase")).toHaveValue("L2");
    expect(screen.getByTestId("entity-phase").tagName).toBe("SELECT");
    fireEvent.change(screen.getByTestId("entity-phase"), { target: { value: "L3" } });
    fireEvent.click(screen.getByRole("button", { name: "Valider" }));
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ phase: "L3" }));
  });

  it("refuse l'option monophasée sur un départ sans neutre", () => {
    render(
      <EntityDialog
        open
        kind="load"
        mode="create"
        project={noNeutralProject}
        initial={null}
        busy={false}
        error={null}
        onSubmit={vi.fn()}
        onClose={() => undefined}
      />,
    );
    const network = screen.getByTestId("entity-network");
    const monoOption = Array.from((network as HTMLSelectElement).options).find(
      (option) => option.value === "MONO",
    );
    expect(monoOption).toBeDisabled();
    expect(screen.getByText(/neutre/i)).toBeInTheDocument();
  });
});
