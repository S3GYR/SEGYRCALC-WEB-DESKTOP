import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ArchitectureScreen } from "../screens/ArchitectureScreen";
import { project } from "./fixtures";
import type { Selection } from "../types";

function ArchitectureHarness() {
  const [selection, setSelection] = useState<Selection | null>(null);
  return (
    <ArchitectureScreen
      project={project}
      selection={selection}
      onSelect={setSelection}
      temporaryEdits={{}}
      onEditDesignation={() => undefined}
      onReset={() => undefined}
      onProjectChanged={() => undefined}
      onToast={() => undefined}
      onUndo={() => undefined}
      onRedo={() => undefined}
      historyBusy={false}
    />
  );
}

describe("intégration architecture / schéma", () => {
  it("conserve l'arborescence et expose le sélecteur graphique", () => {
    render(<ArchitectureHarness />);
    expect(screen.getByTestId("architecture-view-tree")).toBeInTheDocument();
    expect(screen.getByTestId("architecture-view-graph")).toBeInTheDocument();
    expect(screen.getByTestId("tree-view")).toBeInTheDocument();
  });

  it("bascule vers le schéma sans remplacer l'inspecteur", () => {
    render(<ArchitectureHarness />);
    fireEvent.click(screen.getByTestId("tree-board-TGBT-01"));
    fireEvent.click(screen.getByTestId("architecture-view-graph"));
    expect(screen.getByTestId("electrical-graph-view")).toBeInTheDocument();
    expect(screen.getByTestId("property-panel")).toBeInTheDocument();
  });

  it("synchronise une sélection depuis le schéma vers l'arborescence", () => {
    render(<ArchitectureHarness />);
    fireEvent.click(screen.getByTestId("architecture-view-graph"));
    fireEvent.click(screen.getByTestId("graph-node-board-TGBT-01"));
    fireEvent.click(screen.getByTestId("architecture-view-tree"));
    expect(screen.getByTestId("tree-board-TGBT-01").closest(".tree-row")?.className).toContain("is-active");
  });

  it("synchronise une sélection depuis l'arborescence vers le schéma", () => {
    render(<ArchitectureHarness />);
    fireEvent.click(screen.getByTestId("tree-board-TGBT-01"));
    fireEvent.click(screen.getByTestId("architecture-view-graph"));
    expect(screen.getByTestId("graph-node-board-TGBT-01").className).toContain("is-selected");
  });

  it("ne déclenche aucune mutation métier depuis le schéma", () => {
    const onProjectChanged = vi.fn();
    function Harness() {
      const [selection, setSelection] = useState<Selection | null>(null);
      return (
        <ArchitectureScreen
          project={project}
          selection={selection}
          onSelect={setSelection}
          temporaryEdits={{}}
          onEditDesignation={() => undefined}
          onReset={() => undefined}
          onProjectChanged={onProjectChanged}
          onToast={() => undefined}
          onUndo={() => undefined}
          onRedo={() => undefined}
          historyBusy={false}
        />
      );
    }
    render(<Harness />);
    fireEvent.click(screen.getByTestId("architecture-view-graph"));
    fireEvent.click(screen.getByTestId("graph-node-load-REC-01"));
    expect(onProjectChanged).not.toHaveBeenCalled();
  });
});
