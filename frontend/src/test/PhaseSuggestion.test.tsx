import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FeederLoadDialog } from "../components/FeederLoadDialog";
import { suggestPhase } from "../data/phaseSuggestion";
import type { BoardSummary } from "../types";
import { project } from "./fixtures";

function boardWithCharges(l1: string, l2: string, l3: string): BoardSummary {
  return {
    ...project.boards[0],
    current_phases: { l1, l2, l3 },
    p_phases: { l1, l2, l3 },
  };
}

function renderWithCharges(l1: string, l2: string, l3: string, onSubmit = vi.fn()) {
  const board = boardWithCharges(l1, l2, l3);
  render(
    <FeederLoadDialog
      open
      project={{ ...project, boards: [board], loads: [], feeders: [] }}
      parentBoardId={board.id}
      busy={false}
      error={null}
      onSubmit={onSubmit}
      onClose={() => undefined}
    />,
  );
  return onSubmit;
}

describe("suggestPhase", () => {
  it("propose la phase au courant le plus faible", () => {
    const suggestion = suggestPhase(boardWithCharges("1650", "750", "750"));
    expect(suggestion.phase).toBe("L2");
    expect(suggestion.message).toBe("Phase conseillée : L2 — phase actuellement la moins chargée.");
  });

  it("départage les charges identiques de façon déterministe", () => {
    expect(suggestPhase(boardWithCharges("750", "750", "750")).phase).toBe("L1");
  });

  it("utilise la puissance active si les intensités sont indisponibles", () => {
    const board = boardWithCharges("", "", "");
    board.current_phases = { l1: null, l2: null, l3: null };
    board.p_phases = { l1: "1000", l2: "2000", l3: "3000" };
    const suggestion = suggestPhase(board);
    expect(suggestion.phase).toBe("L1");
    expect(suggestion.source).toBe("power");
  });

  it("signale des données insuffisantes", () => {
    const board = boardWithCharges("", "", "");
    board.current_phases = { l1: null, l2: null, l3: null };
    board.p_phases = { l1: null, l2: null, l3: null };
    const suggestion = suggestPhase(board);
    expect(suggestion.phase).toBeNull();
    expect(suggestion.message).toBe("Suggestion de phase indisponible : données de charge insuffisantes.");
  });
});

describe("FeederLoadDialog — suggestion de phase R5", () => {
  it("affiche et présélectionne la phase la moins chargée en MONO_N", () => {
    renderWithCharges("1650", "750", "750");
    fireEvent.change(screen.getByTestId("feeder-load-distribution"), { target: { value: "MONO_N" } });
    expect(screen.getByTestId("feeder-load-phase")).toHaveValue("L2");
    expect(screen.getByTestId("feeder-load-phase-suggestion")).toHaveTextContent("Phase conseillée : L2");
  });

  it("ne remplace pas une sélection manuelle lors d'un changement de puissance", () => {
    renderWithCharges("1650", "750", "750");
    fireEvent.change(screen.getByTestId("feeder-load-distribution"), { target: { value: "MONO_N" } });
    fireEvent.change(screen.getByTestId("feeder-load-phase"), { target: { value: "L1" } });
    fireEvent.change(screen.getByTestId("feeder-load-power"), { target: { value: "5000" } });
    expect(screen.getByTestId("feeder-load-phase")).toHaveValue("L1");
    expect(screen.getByTestId("feeder-load-phase-suggestion")).toHaveTextContent("Phase conseillée : L2");
  });

  it("conserve la sélection manuelle pour un récepteur MONO sur TRI_N", () => {
    renderWithCharges("1650", "750", "750");
    fireEvent.change(screen.getByTestId("feeder-load-distribution"), { target: { value: "TRI_N" } });
    fireEvent.change(screen.getByTestId("feeder-load-network"), { target: { value: "MONO" } });
    expect(screen.getByTestId("feeder-load-load-phase")).toHaveValue("L2");
    fireEvent.change(screen.getByTestId("feeder-load-load-phase"), { target: { value: "L3" } });
    fireEvent.change(screen.getByTestId("feeder-load-power"), { target: { value: "2000" } });
    expect(screen.getByTestId("feeder-load-load-phase")).toHaveValue("L3");
  });

  it("affiche l'indisponibilité et laisse la sélection manuelle", () => {
    const board = boardWithCharges("", "", "");
    board.current_phases = { l1: null, l2: null, l3: null };
    board.p_phases = { l1: null, l2: null, l3: null };
    render(
      <FeederLoadDialog
        open
        project={{ ...project, boards: [board], loads: [], feeders: [] }}
        parentBoardId={board.id}
        busy={false}
        error={null}
        onSubmit={() => undefined}
        onClose={() => undefined}
      />,
    );
    fireEvent.change(screen.getByTestId("feeder-load-distribution"), { target: { value: "MONO_N" } });
    expect(screen.getByTestId("feeder-load-phase-suggestion")).toHaveTextContent(
      "Suggestion de phase indisponible : données de charge insuffisantes.",
    );
    expect(screen.getByTestId("feeder-load-phase")).toHaveValue("L1");
  });

  it("recalcule la suggestion quand la distribution change sans s?lection manuelle", () => {
    renderWithCharges("1650", "750", "750");
    fireEvent.change(screen.getByTestId("feeder-load-distribution"), { target: { value: "TRI_N" } });
    fireEvent.change(screen.getByTestId("feeder-load-network"), { target: { value: "MONO" } });
    expect(screen.getByTestId("feeder-load-load-phase")).toHaveValue("L2");
    fireEvent.change(screen.getByTestId("feeder-load-distribution"), { target: { value: "MONO_N" } });
    expect(screen.getByTestId("feeder-load-phase")).toHaveValue("L2");
  });

  it("ne propose aucune phase pour TRI_NO_N", () => {
    renderWithCharges("1650", "750", "750");
    fireEvent.change(screen.getByTestId("feeder-load-distribution"), { target: { value: "TRI_NO_N" } });
    expect(screen.queryByTestId("feeder-load-phase")).not.toBeInTheDocument();
    expect(screen.queryByTestId("feeder-load-load-phase")).not.toBeInTheDocument();
    expect(screen.queryByTestId("feeder-load-phase-suggestion")).not.toBeInTheDocument();
  });

  it("propose L1 pour un tableau sans charge avec des données disponibles", () => {
    renderWithCharges("0", "0", "0");
    fireEvent.change(screen.getByTestId("feeder-load-distribution"), { target: { value: "MONO_N" } });
    expect(screen.getByTestId("feeder-load-phase")).toHaveValue("L1");
    expect(screen.getByTestId("feeder-load-phase-suggestion")).toHaveTextContent("Phase conseillée : L1");
  });
});
