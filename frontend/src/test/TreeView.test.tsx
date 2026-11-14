import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { TreeView } from "../components/TreeView";
import type { TreeNode } from "../types";

const nodes: TreeNode[] = [
  {
    id: "project",
    kind: "project",
    label: "Projet test",
    meta: "TEST-01",
    status: "OK",
    children: [
      {
        id: "TGBT-01",
        kind: "board",
        label: "Tableau général",
        meta: "TGBT · TRI",
        status: "OK",
        children: [
          {
            id: "DEP-01",
            kind: "feeder",
            label: "Alimentation atelier",
            meta: "DEP-01 · 2 récepteurs",
            status: "OK",
            children: [
              { id: "REC-01", kind: "load", label: "Moteur atelier", meta: "REC-01", status: "OK" },
              { id: "REC-02", kind: "load", label: "Éclairage atelier", meta: "REC-02", status: "OK" },
            ],
          },
        ],
      },
    ],
  },
];

describe("TreeView", () => {
  it("affiche la hiérarchie et sélectionne un nœud", () => {
    const onSelect = vi.fn();
    render(<TreeView nodes={nodes} selection={null} onSelect={onSelect} search="" emptyMessage="Vide" ariaLabel="Arbre" />);
    fireEvent.click(screen.getByTestId("tree-load-REC-01"));
    expect(onSelect).toHaveBeenCalledWith({ kind: "load", id: "REC-01" });
  });

  it("replie et déplie une branche", () => {
    render(<TreeView nodes={nodes} selection={null} onSelect={() => undefined} search="" emptyMessage="Vide" ariaLabel="Arbre" />);
    expect(screen.getByText("Moteur atelier")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Replier Tableau général" }));
    expect(screen.queryByText("Moteur atelier")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Déplier Tableau général" }));
    expect(screen.getByText("Moteur atelier")).toBeInTheDocument();
  });

  it("filtre sur la recherche", () => {
    render(<TreeView nodes={nodes} selection={null} onSelect={() => undefined} search="moteur" emptyMessage="Aucun élément" ariaLabel="Arbre" />);
    expect(screen.getByText("Moteur atelier")).toBeInTheDocument();
    expect(screen.queryByText("Éclairage atelier")).not.toBeInTheDocument();
  });

  it("affiche l’état vide", () => {
    render(<TreeView nodes={nodes} selection={null} onSelect={() => undefined} search="inexistant" emptyMessage="Aucun élément" ariaLabel="Arbre" />);
    expect(screen.getByText("Aucun élément")).toBeInTheDocument();
  });
});
