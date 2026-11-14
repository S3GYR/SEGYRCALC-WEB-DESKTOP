import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { PowerBalanceScreen } from "../screens/PowerBalanceScreen";
import { project } from "./fixtures";
import type { Selection, TemporaryEdits } from "../types";

function Harness() {
  const [selection, setSelection] = useState<Selection | null>({ kind: "board", id: "TGBT-01" });
  const [edits, setEdits] = useState<TemporaryEdits>({});
  return (
    <PowerBalanceScreen
      project={project}
      previousProject={null}
      selection={selection}
      onSelect={setSelection}
      temporaryEdits={edits}
      onEditDesignation={(id, value) => setEdits((current) => ({ ...current, [id]: { designation: value } }))}
      onEditCoefficient={() => undefined}
      onReset={() => setEdits({})}
    />
  );
}

describe("PowerBalanceScreen", () => {
  it("affiche les totaux moteur et le tableau des départs", () => {
    render(<Harness />);
    expect(screen.getByRole("heading", { name: "Le bilan, au centre du travail." })).toBeInTheDocument();
    expect(screen.getAllByText("55,00 kW").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByTestId("balance-tab-feeders"));
    expect(screen.getByTestId("balance-table")).toBeInTheDocument();
    expect(within(screen.getByTestId("balance-table")).getByText("Alimentation atelier")).toBeInTheDocument();
  });

  it("recherche et filtre les départs", () => {
    render(<Harness />);
    fireEvent.click(screen.getByTestId("balance-tab-feeders"));
    const search = screen.getByTestId("balance-search");
    fireEvent.change(search, { target: { value: "éclairage" } });
    const table = screen.getByTestId("balance-table");
    expect(within(table).getByText("Éclairage atelier")).toBeInTheDocument();
    expect(within(table).queryByText("Alimentation atelier")).not.toBeInTheDocument();
    expect(screen.getByText("1 ligne(s)")).toBeInTheDocument();
  });

  it("bascule vers les récepteurs et sélectionne une ligne", () => {
    render(<Harness />);
    fireEvent.click(screen.getByTestId("balance-tab-loads"));
    const table = screen.getByTestId("balance-table");
    expect(within(table).getByText("Moteur atelier")).toBeInTheDocument();
    expect(within(table).getAllByText("Non exposé").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByTestId("row-load-REC-01"));
    const panel = screen.getByTestId("property-panel");
    expect(within(panel).getByText("REC-01")).toBeInTheDocument();
    expect(within(panel).getByText("Moteur atelier")).toBeInTheDocument();
  });

  it("affiche les S/I individuels moteur quand ils sont disponibles", () => {
    const available = {
      ...project,
      loads: project.loads.map((row, index) => ({
        ...row,
        s_after_ks_va: index === 0 ? "1878.26" : "2500",
        current_a: index === 0 ? "8.1663516068" : "10",
        apparent_power_available: true,
        current_available: true,
      })),
    };
    render(
      <PowerBalanceScreen
        project={available}
        previousProject={null}
        selection={{ kind: "load", id: "REC-01" }}
        onSelect={() => undefined}
        temporaryEdits={{}}
        onEditDesignation={() => undefined}
        onEditCoefficient={() => undefined}
        onReset={() => undefined}
      />,
    );
    fireEvent.click(screen.getByTestId("balance-tab-loads"));
    const table = screen.getByTestId("balance-table");
    expect(within(table).getByText("1,88 kVA")).toBeInTheDocument();
    expect(within(table).getByText("8,17 A")).toBeInTheDocument();
    expect(within(table).queryByText("Non exposé")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("row-load-REC-01"));
    const panel = screen.getByTestId("property-panel");
    expect(within(panel).getByText("1,88 kVA")).toBeInTheDocument();
    expect(within(panel).getByText("8,17 A")).toBeInTheDocument();
  });

  it("affiche les vues tableaux et TGBT avec la synthèse moteur", () => {
    render(<Harness />);
    fireEvent.click(screen.getByTestId("balance-tab-boards"));
    expect(within(screen.getByTestId("balance-table")).getByText("Tableau général")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("balance-tab-tgbt"));
    expect(screen.getByTestId("tgbt-summary")).toBeInTheDocument();
    expect(screen.getByText("Cos φ global")).toBeInTheDocument();
    expect(screen.getByTestId("phase-balance-panel")).toBeInTheDocument();
  });

  it("édite Ks via la commande de coefficient", () => {
    const onEditCoefficient = vi.fn();
    render(
      <PowerBalanceScreen
        project={project}
        previousProject={null}
        selection={{ kind: "feeder", id: "DEP-01" }}
        onSelect={() => undefined}
        temporaryEdits={{}}
        onEditDesignation={() => undefined}
        onEditCoefficient={onEditCoefficient}
        onReset={() => undefined}
      />,
    );
    fireEvent.change(screen.getByTestId("coefficient-input"), { target: { value: "0.75" } });
    fireEvent.click(screen.getByTestId("coefficient-apply"));
    expect(onEditCoefficient).toHaveBeenCalledWith("feeder", "DEP-01", "0.75");
  });

  it("affiche la comparaison avant/après et la traçabilité", () => {
    const previous = {
      ...project,
      state: { ...project.state, revision: 1 },
      totals: { ...project.totals, p_after_ks_w: "40000", s_after_ks_va: "47000" },
    };
    render(
      <PowerBalanceScreen
        project={project}
        previousProject={previous}
        selection={null}
        onSelect={() => undefined}
        temporaryEdits={{}}
        onEditDesignation={() => undefined}
        onEditCoefficient={() => undefined}
        onReset={() => undefined}
      />,
    );
    expect(screen.getByTestId("comparison-panel")).toBeInTheDocument();
    expect(screen.getByTestId("traceability-panel")).toBeInTheDocument();
  });

  it("applique une modification locale de désignation", () => {
    render(<Harness />);
    fireEvent.click(screen.getByTestId("balance-tab-loads"));
    fireEvent.click(screen.getByTestId("row-load-REC-01"));
    const input = screen.getByLabelText("Désignation");
    fireEvent.change(input, { target: { value: "Moteur atelier temporaire" } });
    fireEvent.click(screen.getByRole("button", { name: "Appliquer" }));
    expect(screen.getAllByText("Moteur atelier temporaire").length).toBeGreaterThan(0);
    expect(screen.getByText("Non enregistrée")).toBeInTheDocument();
    expect(screen.getByText(/Modification locale/)).toBeInTheDocument();
  });
});
