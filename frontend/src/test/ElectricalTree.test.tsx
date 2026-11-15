import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { buildElectricalTree } from "../data/hierarchy";
import { TreeView } from "../components/TreeView";
import { PropertyContent } from "../screens/PropertyContent";
import { load, project } from "./fixtures";
import type { LoadSummary, ProjectPayload, TreeNode } from "../types";

const unassigned: LoadSummary = {
  ...load,
  id: "REC-U1",
  designation: "Récepteur non affecté",
  feeder_id: "",
  parent_board_id: "",
};

function withUnassigned(loads: LoadSummary[] | undefined, count = 1): ProjectPayload {
  return {
    ...project,
    unassigned_loads: loads,
    project: { ...project.project, unassigned_load_count: count },
    coherence: {
      ...project.coherence,
      unassigned_load_ids: Array.from({ length: count }, (_, index) => `REC-U${index + 1}`),
    },
  };
}

describe("arborescence électrique consolidée", () => {
  it("transforme un départ vide en état non sélectionnable", () => {
    const emptyProject: ProjectPayload = {
      ...project,
      feeders: [{ ...project.feeders[0], id: "DEP-EMPTY", member_count: 0 }],
      loads: [],
    };
    const tree = buildElectricalTree(emptyProject);
    const boardNode = tree[0].children?.[0];
    const feeder = boardNode?.children?.find((node) => node.id === "DEP-EMPTY");
    const empty = feeder?.children?.[0];
    expect(empty?.kind).toBe("empty");
    expect(empty?.selectable).toBe(false);
    expect(empty?.selection).toBeUndefined();
  });

  it("ne déclenche aucune sélection depuis l'état vide", () => {
    const emptyProject: ProjectPayload = {
      ...project,
      feeders: [{ ...project.feeders[0], id: "DEP-EMPTY", member_count: 0 }],
      loads: [],
    };
    const onSelect = vi.fn();
    render(
      <TreeView
        nodes={buildElectricalTree(emptyProject)}
        selection={null}
        onSelect={onSelect}
        search=""
        emptyMessage="Vide"
        ariaLabel="Arbre"
      />,
    );
    fireEvent.click(screen.getByTestId("tree-empty-empty:DEP-EMPTY"));
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("affiche une section de récepteurs non affectés quand les objets sont fournis", () => {
    const tree = buildElectricalTree(withUnassigned([unassigned]));
    const group = tree[0].children?.find((node) => node.kind === "unassigned-group");
    expect(group?.label).toContain("1");
    expect(group?.selectable).toBe(false);
    expect(group?.children?.[0].selection).toEqual({ kind: "load", id: "REC-U1" });
    expect(group?.children?.[0].selectable).toBe(true);
  });

  it("conserve simultanément les récepteurs affectés et la section non affectée", () => {
    const tree = buildElectricalTree(withUnassigned([unassigned]));
    const boardNode = tree[0].children?.find((node) => node.id === "TGBT-01");
    const group = tree[0].children?.find((node) => node.kind === "unassigned-group");
    expect(boardNode?.children?.length).toBeGreaterThan(0);
    expect(group?.children?.[0].selection).toEqual({ kind: "load", id: "REC-U1" });
  });

  it("recherche un récepteur non affecté par son identifiant", () => {
    render(
      <TreeView
        nodes={buildElectricalTree(withUnassigned([unassigned]))}
        selection={null}
        onSelect={() => undefined}
        search="REC-U1"
        emptyMessage="Vide"
        ariaLabel="Arbre"
      />,
    );
    expect(screen.getByText("Récepteur non affecté")).toBeInTheDocument();
  });

  it("affiche les propriétés d'un récepteur non affecté dans l'inspecteur", () => {
    render(
      <PropertyContent
        project={withUnassigned([unassigned])}
        selection={{ kind: "load", id: "REC-U1" }}
        temporaryEdits={{}}
        onEditDesignation={() => undefined}
        onReset={() => undefined}
      />,
    );
    expect(screen.getByText("Récepteur non affecté")).toBeInTheDocument();
    expect(screen.getByText("REC-U1")).toBeInTheDocument();
    expect(screen.getByText("Ku")).toBeInTheDocument();
  });

  it("affiche le nombre annoncé sans inventer de récepteur si le détail manque", () => {
    const tree = buildElectricalTree(withUnassigned(undefined, 3));
    const group = tree[0].children?.find((node) => node.kind === "unassigned-group");
    expect(group?.label).toContain("3");
    expect(group?.children ?? []).toHaveLength(0);
    expect(group?.selectable).toBe(false);
  });

  it("conserve l'identité de sélection des tableaux, départs et récepteurs", () => {
    const tree = buildElectricalTree(project);
    const boardNode = tree[0].children?.[0];
    const feederNode = boardNode?.children?.[0];
    const loadNode = feederNode?.children?.[0];
    expect(boardNode?.selection).toEqual({ kind: "board", id: "TGBT-01" });
    expect(feederNode?.selection).toEqual({ kind: "feeder", id: "DEP-01" });
    expect(loadNode?.selection).toEqual({ kind: "load", id: "REC-01" });
  });

  it("distingue deux entités de même identifiant par leur kind", () => {
    const nodes: TreeNode[] = [
      {
        id: "SAME",
        kind: "board",
        label: "Tableau",
        meta: "SAME",
        status: "OK",
        selection: { kind: "board", id: "SAME" },
        selectable: true,
      },
      {
        id: "SAME",
        kind: "load",
        label: "Récepteur",
        meta: "SAME",
        status: "OK",
        selection: { kind: "load", id: "SAME" },
        selectable: true,
      },
    ];
    render(
      <TreeView
        nodes={nodes}
        selection={{ kind: "board", id: "SAME" }}
        onSelect={() => undefined}
        search=""
        emptyMessage="Vide"
        ariaLabel="Arbre"
      />,
    );
    expect(screen.getByTestId("tree-board-SAME").getAttribute("aria-current")).toBe("true");
    expect(screen.getByTestId("tree-load-SAME").getAttribute("aria-current")).toBeNull();
  });
});
