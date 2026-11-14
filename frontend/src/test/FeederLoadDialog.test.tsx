import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FeederLoadDialog } from "../components/FeederLoadDialog";
import { project } from "./fixtures";

function renderDialog(onSubmit = vi.fn()) {
  render(
    <FeederLoadDialog
      open
      project={project}
      parentBoardId="TGBT-01"
      busy={false}
      error={null}
      onSubmit={onSubmit}
      onClose={() => undefined}
    />,
  );
  return onSubmit;
}

describe("FeederLoadDialog — formulaire unifié R4", () => {
  it("affiche un seul formulaire compact et le bon titre", () => {
    renderDialog();
    expect(screen.getByRole("heading", { name: "Créer un départ électrique" })).toBeInTheDocument();
    expect(screen.getByTestId("feeder-load-unified-form")).toBeInTheDocument();
    expect(screen.queryByText("Section A")).not.toBeInTheDocument();
    expect(screen.queryByText("Section B")).not.toBeInTheDocument();
    expect(screen.queryByText("Premier récepteur")).not.toBeInTheDocument();
    expect(screen.queryByTestId("feeder-load-load-designation")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Créer le départ" })).toBeInTheDocument();
  });

  it("préremplit Q1 et n'affiche aucune erreur avant interaction", () => {
    renderDialog();
    expect(screen.getByTestId("feeder-load-feeder-reference")).toHaveValue("Q1");
    expect(screen.queryByTestId("feeder-load-reference-error")).not.toBeInTheDocument();
    expect(screen.queryByTestId("feeder-load-designation-error")).not.toBeInTheDocument();
    expect(screen.getByTestId("feeder-load-submit")).toBeDisabled();
  });

  it("utilise une seule désignation pour les deux objets", () => {
    const onSubmit = renderDialog();
    fireEvent.change(screen.getByTestId("feeder-load-designation"), { target: { value: "Éclairage" } });
    fireEvent.change(screen.getByTestId("feeder-load-power"), { target: { value: "1500" } });
    fireEvent.change(screen.getByTestId("feeder-load-ks"), { target: { value: "0.8" } });
    fireEvent.change(screen.getByTestId("feeder-load-ku"), { target: { value: "0.7" } });
    fireEvent.click(screen.getByTestId("feeder-load-submit"));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        parent_board_id: "TGBT-01",
        feeder: expect.objectContaining({
          reference: "Q1",
          auto_reference: true,
          designation: "Éclairage",
          ks: "0.8",
        }),
        load: expect.objectContaining({
          designation: "Éclairage",
          nominal_power: "1500",
          quantity: 1,
          ku: "0.7",
        }),
      }),
    );
  });

  it("crée un couple TRI_NO_N sans phase monophasée", () => {
    const onSubmit = renderDialog();
    fireEvent.change(screen.getByTestId("feeder-load-designation"), { target: { value: "Chauffage" } });
    fireEvent.change(screen.getByTestId("feeder-load-distribution"), { target: { value: "TRI_NO_N" } });
    fireEvent.click(screen.getByTestId("feeder-load-submit"));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        feeder: expect.objectContaining({ distribution_type: "TRI_NO_N", phase: null }),
        load: expect.objectContaining({ network: "TRI", phase: null, voltage_v: "400" }),
      }),
    );
  });

  it("hérite la phase et la tension du départ MONO_N", () => {
    const onSubmit = renderDialog();
    fireEvent.change(screen.getByTestId("feeder-load-designation"), { target: { value: "Éclairage" } });
    fireEvent.change(screen.getByTestId("feeder-load-distribution"), { target: { value: "MONO_N" } });
    fireEvent.change(screen.getByTestId("feeder-load-phase"), { target: { value: "L2" } });
    expect(screen.getByTestId("feeder-load-phase")).toHaveValue("L2");
    expect(screen.getByTestId("feeder-load-load-voltage")).toHaveValue("230");
    fireEvent.click(screen.getByTestId("feeder-load-submit"));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        feeder: expect.objectContaining({ distribution_type: "MONO_N", phase: "L2" }),
        load: expect.objectContaining({ network: "MONO", phase: "L2", voltage_v: "230" }),
      }),
    );
  });

  it("permet un récepteur monophasé sur TRI_N avec neutre", () => {
    const onSubmit = renderDialog();
    fireEvent.change(screen.getByTestId("feeder-load-designation"), { target: { value: "Prise" } });
    fireEvent.change(screen.getByTestId("feeder-load-distribution"), { target: { value: "TRI_N" } });
    fireEvent.change(screen.getByTestId("feeder-load-network"), { target: { value: "MONO" } });
    fireEvent.change(screen.getByTestId("feeder-load-load-phase"), { target: { value: "L3" } });
    fireEvent.click(screen.getByTestId("feeder-load-submit"));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        load: expect.objectContaining({ network: "MONO", phase: "L3", voltage_v: "230" }),
      }),
    );
  });

  it("affiche une erreur de champ et conserve les valeurs invalides", () => {
    renderDialog();
    fireEvent.change(screen.getByTestId("feeder-load-designation"), { target: { value: "Éclairage" } });
    fireEvent.change(screen.getByTestId("feeder-load-power"), { target: { value: "0" } });
    expect(screen.getByTestId("feeder-load-designation")).toHaveValue("Éclairage");
    expect(screen.getByTestId("feeder-load-power")).toHaveValue("0");
    expect(screen.queryByTestId("feeder-load-designation-error")).not.toBeInTheDocument();
    expect(screen.getByText("La puissance doit être strictement positive.")).toBeInTheDocument();
    expect(screen.getByTestId("feeder-load-submit")).toBeDisabled();
  });

  it("propose Q4 lorsque Q1 et Q3 existent déjà", () => {
    const projectWithReferences = {
      ...project,
      feeders: [
        { ...project.feeders[0], reference: "Q1" },
        { ...project.feeders[0], id: "DEP-03", reference: "Q3" },
      ],
      loads: [],
    };
    render(
      <FeederLoadDialog
        open
        project={projectWithReferences}
        parentBoardId="TGBT-01"
        busy={false}
        error={null}
        onSubmit={() => undefined}
        onClose={() => undefined}
      />,
    );
    expect(screen.getByTestId("feeder-load-feeder-reference")).toHaveValue("Q4");
  });
});
