import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ElectricalGraphView } from "../components/ElectricalGraphView";
import { load, project } from "./fixtures";
import type { LoadSummary, ProjectPayload, Selection } from "../types";

function unassignedProject(): ProjectPayload {
  const unassigned: LoadSummary = {
    ...load,
    id: "REC-U-GRAPH",
    designation: "Récepteur hors affectation",
    feeder_id: "",
    parent_board_id: "",
  };
  return {
    ...project,
    unassigned_loads: [unassigned],
    project: { ...project.project, unassigned_load_count: 1 },
    coherence: { ...project.coherence, unassigned_load_ids: ["REC-U-GRAPH"] },
  };
}

function renderGraph(
  input: ProjectPayload = project,
  selection: Selection | null = null,
  onSelect: (selection: Selection) => void = () => undefined,
) {
  return render(<ElectricalGraphView project={input} selection={selection} onSelect={onSelect} />);
}

describe("ElectricalGraphView", () => {
  it("rend le TGBT, les départs et les récepteurs", () => {
    renderGraph();
    expect(screen.getByTestId("electrical-graph-view")).toBeInTheDocument();
    expect(screen.getByTestId("graph-node-board-TGBT-01")).toBeInTheDocument();
    expect(screen.getByTestId("graph-node-feeder-DEP-01")).toBeInTheDocument();
    expect(screen.getByTestId("graph-node-load-REC-01")).toBeInTheDocument();
  });

  it("sélectionne un équipement depuis le graphe", () => {
    const onSelect = vi.fn();
    renderGraph(project, null, onSelect);
    fireEvent.click(screen.getByTestId("graph-node-feeder-DEP-01"));
    expect(onSelect).toHaveBeenCalledWith({ kind: "feeder", id: "DEP-01" });
  });

  it("met en évidence la sélection partagée", () => {
    renderGraph(project, { kind: "board", id: "TGBT-01" });
    expect(screen.getByTestId("graph-node-board-TGBT-01").className).toContain("is-selected");
    expect(screen.getByTestId("graph-node-feeder-DEP-01").className).not.toContain("is-selected");
  });

  it("rend les non affectés sans connexion électrique", () => {
    renderGraph(unassignedProject());
    expect(screen.getByTestId("graph-node-unassigned-group-unassigned")).toBeInTheDocument();
    expect(screen.getByTestId("graph-node-load-REC-U-GRAPH")).toBeInTheDocument();
    expect(screen.getByTestId("graph-node-unassigned-group-unassigned")).toHaveTextContent(/NON AFFECT/i);
  });

  it("expose les diagnostics structurels", () => {
    renderGraph();
    expect(screen.getByTestId("graph-diagnostics")).toBeInTheDocument();
    expect(screen.getByText(/1 avertissement/)).toBeInTheDocument();
  });

  it("ne mute pas le projet pendant le rendu", () => {
    const before = JSON.stringify(project);
    const view = renderGraph();
    expect(JSON.stringify(project)).toBe(before);
    view.unmount();
    expect(JSON.stringify(project)).toBe(before);
  });

  it("reste en lecture seule et n'ouvre aucune ligne de connexion", () => {
    const { container } = renderGraph();
    expect(container.querySelectorAll(".react-flow__handle").length).toBeGreaterThan(0);
    expect(container.querySelector(".react-flow__connectionline")).toBeNull();
  });

  it("rend un état vide sans inventer de nÅ“ud métier", () => {
    const empty: ProjectPayload = {
      ...project,
      boards: [],
      feeders: [],
      loads: [],
      project: { ...project.project, board_count: 0, feeder_count: 0, load_count: 0 },
    };
    renderGraph(empty);
    expect(screen.getByTestId("electrical-graph-view")).toBeInTheDocument();
    expect(screen.queryByTestId("graph-node-board-TGBT-01")).not.toBeInTheDocument();
    expect(screen.getByTestId("graph-diagnostics")).toBeInTheDocument();
  });

  it("replie une branche, affiche le nombre masqué et la développe", () => {
    renderGraph();
    expect(screen.getByTestId("graph-node-load-REC-01")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("graph-toggle-DEP-01"));
    expect(screen.queryByTestId("graph-node-load-REC-01")).not.toBeInTheDocument();
    expect(screen.getByTestId("graph-node-feeder-DEP-02")).toBeInTheDocument();
    expect(screen.getByText(/2 descendants/)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("graph-toggle-DEP-01"));
    expect(screen.getByTestId("graph-node-load-REC-01")).toBeInTheDocument();
  });

  it("développe et réduit toutes les branches sans changer les données", () => {
    const before = JSON.stringify(project);
    renderGraph();
    fireEvent.click(screen.getByTestId("graph-collapse-all"));
    expect(screen.queryByTestId("graph-node-load-REC-01")).not.toBeInTheDocument();
    expect(screen.getByTestId("graph-node-board-TGBT-01")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("graph-expand-all"));
    expect(screen.getByTestId("graph-node-load-REC-01")).toBeInTheDocument();
    expect(JSON.stringify(project)).toBe(before);
  });

  it("affiche un périmètre de tableau avec fil d'Ariane et retour global", () => {
    function Harness() {
      const [selection, setSelection] = useState<Selection | null>(null);
      return <ElectricalGraphView project={project} selection={selection} onSelect={setSelection} />;
    }
    render(<Harness />);
    fireEvent.click(screen.getByTestId("graph-node-feeder-DEP-02"));
    fireEvent.click(screen.getByTestId("graph-scope-selection"));
    expect(screen.getByTestId("graph-view-context")).toHaveTextContent(/clairage atelier/);
    expect(screen.getByText("Installation")).toBeInTheDocument();
    expect(screen.getByTestId("graph-node-board-TGBT-01")).toBeInTheDocument();
    expect(screen.getByTestId("graph-node-feeder-DEP-02")).toBeInTheDocument();
    expect(screen.queryByTestId("graph-node-feeder-DEP-01")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("graph-scope-all"));
    expect(screen.getByTestId("graph-node-feeder-DEP-01")).toBeInTheDocument();
  });

  it("révèle une sélection masquée par le repli sans changer la sélection", () => {
    const onSelect = vi.fn();
    renderGraph(project, { kind: "load", id: "REC-01" }, onSelect);
    fireEvent.click(screen.getByTestId("graph-toggle-DEP-01"));
    expect(screen.getByTestId("graph-hidden-selection")).toBeInTheDocument();
    expect(screen.queryByTestId("graph-node-load-REC-01")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("graph-reveal-selection"));
    expect(screen.getByTestId("graph-node-load-REC-01")).toBeInTheDocument();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("expose les commandes Fit View sans modifier le projet", () => {
    const before = JSON.stringify(project);
    renderGraph();
    expect(screen.getByTestId("graph-fit")).toBeInTheDocument();
    expect(screen.getByTestId("graph-fit-selection")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("graph-fit"));
    fireEvent.click(screen.getByTestId("graph-fit-selection"));
    expect(JSON.stringify(project)).toBe(before);
  });

  it("agrège la vue synthétique et ouvre le périmètre du tableau", () => {
    renderGraph();
    fireEvent.click(screen.getByTestId("graph-mode-progressive"));
    expect(screen.getByTestId("graph-node-aggregate-aggregate:board-branches:TGBT-01")).toBeInTheDocument();
    expect(screen.queryByTestId("graph-node-load-REC-01")).not.toBeInTheDocument();
    expect(screen.queryByTestId("graph-node-feeder-DEP-01")).not.toBeInTheDocument();
    expect(screen.getByTestId("graph-node-aggregate-aggregate:board-branches:TGBT-01")).toHaveTextContent(/2 départ/);
    fireEvent.click(screen.getByTestId("graph-aggregate-open-board:TGBT-01"));
    expect(screen.getByTestId("graph-view-context")).toHaveTextContent("Tableau général");
    expect(screen.getByTestId("graph-node-board-TGBT-01")).toBeInTheDocument();
    expect(screen.getByTestId("graph-node-feeder-DEP-01")).toBeInTheDocument();
    expect(screen.getByTestId("graph-node-feeder-DEP-02")).toBeInTheDocument();
    expect(screen.queryByTestId("graph-node-load-REC-01")).not.toBeInTheDocument();
  });

  it("descend du tableau au départ puis à l'équipement", () => {
    function Harness() {
      const [selection, setSelection] = useState<Selection | null>(null);
      return <ElectricalGraphView project={project} selection={selection} onSelect={setSelection} />;
    }
    render(<Harness />);
    fireEvent.click(screen.getByTestId("graph-mode-progressive"));
    fireEvent.click(screen.getByTestId("graph-aggregate-open-board:TGBT-01"));
    fireEvent.click(screen.getByTestId("graph-node-feeder-DEP-01"));
    fireEvent.click(screen.getByTestId("graph-scope-selection"));
    expect(screen.getByTestId("graph-view-context")).toHaveTextContent(/Alimentation atelier/);
    expect(screen.getByTestId("graph-node-load-REC-01")).toBeInTheDocument();
    expect(screen.getByTestId("graph-node-load-REC-02")).toBeInTheDocument();
  });

  it("révèle depuis la vue synthétique un équipement masqué par agrégation", () => {
    const onSelect = vi.fn();
    renderGraph(project, { kind: "load", id: "REC-01" }, onSelect);
    fireEvent.click(screen.getByTestId("graph-mode-progressive"));
    expect(screen.getByTestId("graph-hidden-selection")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("graph-reveal-selection"));
    expect(screen.getByTestId("graph-node-load-REC-01")).toBeInTheDocument();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("revient à la vue complète sans mutation", () => {
    const before = JSON.stringify(project);
    renderGraph();
    fireEvent.click(screen.getByTestId("graph-mode-progressive"));
    fireEvent.click(screen.getByTestId("graph-mode-full"));
    expect(screen.getByTestId("graph-node-load-REC-01")).toBeInTheDocument();
    expect(JSON.stringify(project)).toBe(before);
  });
});
