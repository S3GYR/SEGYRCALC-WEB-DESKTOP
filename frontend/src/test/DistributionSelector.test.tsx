import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { EntityDialog } from "../components/EntityDialog";
import {
  allowedDistributionTypes,
  defaultDistributionType,
  distributionFromFeeder,
  type DistributionType,
} from "../data/distribution";
import { board, project } from "./fixtures";

const triWithNeutral = {
  ...board,
  network: "TRI",
  has_neutral: true,
  phase_voltage_v: "230",
};
const triWithoutNeutral = {
  ...board,
  network: "TRI",
  has_neutral: false,
  phase_voltage_v: null,
};
const monophase = {
  ...board,
  network: "MONO",
  has_neutral: true,
  voltage_v: "230",
  phase_voltage_v: "230",
};

describe("règles de distribution", () => {
  it("applique la compatibilité du tableau parent", () => {
    expect(allowedDistributionTypes(triWithNeutral)).toEqual(["TRI_NO_N", "MONO_N", "TRI_N"]);
    expect(allowedDistributionTypes(triWithoutNeutral)).toEqual(["TRI_NO_N"]);
    expect(allowedDistributionTypes(monophase)).toEqual(["MONO_N"]);
    expect(allowedDistributionTypes({ ...monophase, has_neutral: false })).toEqual([]);
    expect(defaultDistributionType(triWithNeutral)).toBe("TRI_N");
    expect(defaultDistributionType(triWithoutNeutral)).toBe("TRI_NO_N");
  });

  it("déduit le type d'un départ existant", () => {
    expect(distributionFromFeeder({ network: "MONO", has_neutral: true })).toBe("MONO_N");
    expect(distributionFromFeeder({ network: "TRI", has_neutral: true })).toBe("TRI_N");
    expect(distributionFromFeeder({ network: "TRI", has_neutral: false })).toBe("TRI_NO_N");
  });
});

describe("EntityDialog — type de départ", () => {
  it("affiche la phase uniquement pour MONO_N et envoie le bon contrat", () => {
    const onSubmit = vi.fn();
    render(
      <EntityDialog
        open
        kind="feeder"
        mode="create"
        project={project}
        initial={null}
        busy={false}
        error={null}
        onSubmit={onSubmit}
        onClose={() => undefined}
      />,
    );
    fireEvent.change(screen.getByTestId("entity-designation"), { target: { value: "Départ test" } });
    fireEvent.change(screen.getByTestId("entity-distribution"), { target: { value: "MONO_N" } });
    expect(screen.getByTestId("entity-phase")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("entity-phase"), { target: { value: "L2" } });
    fireEvent.click(screen.getByRole("button", { name: "Valider" }));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        distribution_type: "MONO_N",
        phase: "L2",
      }),
    );

    fireEvent.change(screen.getByTestId("entity-distribution"), { target: { value: "TRI_N" } });
    expect(screen.queryByTestId("entity-phase")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Valider" }));
    expect(onSubmit).toHaveBeenLastCalledWith(
      expect.objectContaining({
        distribution_type: "TRI_N",
        phase: null,
      }),
    );
  });

  it("désactive la validation si aucune distribution n'est compatible", () => {
    const noNeutral = {
      ...project,
      boards: [{ ...project.boards[0], network: "MONO", has_neutral: false, phase_voltage_v: "230" }],
    };
    render(
      <EntityDialog
        open
        kind="feeder"
        mode="create"
        project={noNeutral}
        initial={null}
        busy={false}
        error={null}
        onSubmit={vi.fn()}
        onClose={() => undefined}
      />,
    );
    fireEvent.change(screen.getByTestId("entity-designation"), { target: { value: "Départ test" } });
    expect(screen.getByTestId("entity-distribution")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Valider" })).toBeDisabled();
  });

  it("conserve les options typées du contrat", () => {
    const types: DistributionType[] = ["MONO_N", "TRI_NO_N", "TRI_N"];
    expect(types).toHaveLength(3);
  });
});
