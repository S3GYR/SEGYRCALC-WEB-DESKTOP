import { describe, expect, it } from "vitest";
import { buildElectricalGraph, type ElectricalGraph, type ElectricalGraphNode } from "../data/electricalGraph";
import {
  GRAPH_NODE_HEIGHT,
  GRAPH_NODE_WIDTH,
  computeFitViewport,
  layoutBounds,
  layoutElectricalGraph,
} from "../data/electricalGraphLayout";
import { load, project } from "./fixtures";
import type { LoadSummary, ProjectPayload } from "../types";

function withUnassigned(loads: LoadSummary[], count = loads.length): ProjectPayload {
  return {
    ...project,
    unassigned_loads: loads,
    project: { ...project.project, unassigned_load_count: count },
    coherence: {
      ...project.coherence,
      unassigned_load_ids: loads.map((item) => item.id),
    },
  };
}

const unassigned: LoadSummary = {
  ...load,
  id: "REC-U-LAYOUT",
  designation: "Récepteur non affecté",
  feeder_id: "",
  parent_board_id: "",
};

function syntheticLargeGraph(count: number): ElectricalGraph {
  const feederCount = Math.floor((count - 1) / 2);
  const loadCount = count - 1 - feederCount;
  const metrics = {
    p_installed_w: null,
    p_after_ku_w: null,
    p_after_ks_w: null,
    q_after_ks_var: null,
    s_after_ks_va: null,
    current_a: null,
    neutral_current_a: null,
    unbalance_percent: null,
  };
  const node = (id: string, kind: ElectricalGraphNode["kind"]): ElectricalGraphNode => ({
    id,
    kind,
    entityId: id.split(":")[1] ?? null,
    label: id,
    meta: "",
    status: "OK",
    selectable: true,
    metrics,
  });
  const nodes = [node("board:ROOT", "board")];
  const edges: ElectricalGraph["edges"] = [];
  for (let index = 0; index < feederCount; index += 1) {
    const feederId = `feeder:F-${index}`;
    nodes.push(node(feederId, "feeder"));
    edges.push({
      id: `e-board-${index}`,
      kind: "board-to-feeder",
      source: "board:ROOT",
      target: feederId,
      feederId: `F-${index}`,
      label: "",
      status: "OK",
    });
  }
  for (let index = 0; index < loadCount; index += 1) {
    const loadId = `load:L-${index}`;
    const feederId = `feeder:F-${index % feederCount}`;
    nodes.push(node(loadId, "load"));
    edges.push({
      id: `e-load-${index}`,
      kind: "feeder-to-load",
      source: feederId,
      target: loadId,
      feederId: `F-${index % feederCount}`,
      label: "",
      status: "OK",
    });
  }
  return { nodes, edges, diagnostics: [] };
}

describe("layout graphique déterministe", () => {
  it("place le TGBT avant les départs et les récepteurs", () => {
    const graph = buildElectricalGraph(project);
    const layout = layoutElectricalGraph(graph);
    expect(layout.levels["board:TGBT-01"]).toBe(0);
    expect(layout.levels["feeder:DEP-01"]).toBe(1);
    expect(layout.levels["load:REC-01"]).toBe(2);
    expect(layout.maxLevel).toBeGreaterThanOrEqual(2);
  });

  it("ne superpose aucun nÅ“ud, y compris avec plusieurs rangées", () => {
    const graph = buildElectricalGraph(project);
    const layout = layoutElectricalGraph(graph);
    for (let left = 0; left < graph.nodes.length; left += 1) {
      const leftPosition = layout.positions[graph.nodes[left].id];
      for (let right = left + 1; right < graph.nodes.length; right += 1) {
        const rightPosition = layout.positions[graph.nodes[right].id];
        const overlapsX = Math.abs(leftPosition.x - rightPosition.x) < GRAPH_NODE_WIDTH;
        const overlapsY = Math.abs(leftPosition.y - rightPosition.y) < GRAPH_NODE_HEIGHT;
        expect(overlapsX && overlapsY).toBe(false);
      }
    }
  });

  it("est déterministe pour le même graphe", () => {
    const graph = buildElectricalGraph(project);
    expect(layoutElectricalGraph(graph)).toEqual(layoutElectricalGraph(graph));
  });

  it("ne mute pas le graphe", () => {
    const graph = buildElectricalGraph(project);
    const before = JSON.stringify(graph);
    layoutElectricalGraph(graph);
    expect(JSON.stringify(graph)).toBe(before);
  });

  it("place le groupe non affecté dans une zone après la hiérarchie", () => {
    const graph = buildElectricalGraph(withUnassigned([unassigned]));
    const layout = layoutElectricalGraph(graph);
    expect(layout.levels["group:unassigned"]).toBeGreaterThan(layout.levels["board:TGBT-01"]);
    expect(layout.levels["load:REC-U-LAYOUT"]).toBeGreaterThanOrEqual(layout.levels["group:unassigned"]);
    expect(graph.edges.some((edge) => edge.target === "load:REC-U-LAYOUT")).toBe(false);
  });

  it("place tous les nÅ“uds pour un graphe sans tableau", () => {
    const graph = buildElectricalGraph({
      ...project,
      boards: [],
      feeders: [],
      loads: [],
      project: { ...project.project, board_count: 0, feeder_count: 0, load_count: 0 },
    });
    const layout = layoutElectricalGraph(graph);
    expect(layout.positions).toEqual({});
    expect(layout.maxLevel).toBe(-1);
  });

  it("borne la largeur et évite les chevauchements à 1000 nœuds", () => {
    const graph = syntheticLargeGraph(1000);
    const layout = layoutElectricalGraph(graph);
    const positions = Object.values(layout.positions);
    expect(positions).toHaveLength(1000);
    expect(new Set(positions.map((point) => `${point.x}:${point.y}`)).size).toBe(1000);
    expect(layout.width).toBeLessThan(10000);
    expect(layout.rowsByLevel[1]).toBeGreaterThan(1);
    expect(layout.columnsByLevel[1]).toBeGreaterThan(1);
  });

  it("calcule un Fit View déterministe depuis les positions de layout", () => {
    const graph = syntheticLargeGraph(1000);
    const layout = layoutElectricalGraph(graph);
    const ids = new Set(Object.keys(layout.positions));
    const bounds = layoutBounds(layout, ids);
    expect(bounds).not.toBeNull();
    const viewport = computeFitViewport(bounds!, 1000, 500, 0.18, 0.1, 1.2);
    expect(viewport).not.toBeNull();
    expect(viewport!.zoom).toBeGreaterThanOrEqual(0.1);
    expect(viewport!.zoom).toBeLessThanOrEqual(1.2);
    expect(computeFitViewport(bounds!, 1000, 500, 0.18, 0.1, 1.2)).toEqual(viewport);
  });
});
