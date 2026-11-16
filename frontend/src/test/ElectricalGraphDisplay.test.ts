import { describe, expect, it } from "vitest";
import { buildElectricalGraph } from "../data/electricalGraph";
import { buildDisplayGraph } from "../data/electricalGraphDisplay";
import { project } from "./fixtures";

describe("agrégation graphique progressive", () => {
  const graph = buildElectricalGraph(project);

  it("agrège les branches terminales de l'installation sans perdre les identities", () => {
    const before = JSON.stringify(graph);
    const display = buildDisplayGraph(graph, { scope: null, mode: "progressive" });
    expect(display.nodes.find((node) => node.id === "board:TGBT-01")).toBeDefined();
    expect(display.nodes.some((node) => node.kind === "load")).toBe(false);
    expect(display.nodes.some((node) => node.kind === "feeder")).toBe(false);
    const aggregate = display.nodes.find((node) => node.kind === "aggregate");
    expect(aggregate?.aggregate).toMatchObject({
      parentNodeId: "board:TGBT-01",
      feederCount: 2,
      loadCount: 2,
      targetKind: "board",
      targetId: "TGBT-01",
    });
    expect(display.edges).toHaveLength(1);
    expect(display.edges[0].kind).toBe("aggregated");
    expect(display.edges[0].source).toBe("board:TGBT-01");
    expect(display.hiddenRealNodeIds.has("load:REC-01")).toBe(true);
    expect(JSON.stringify(graph)).toBe(before);
  });

  it("ne crée aucune liaison directe entre le TGBT et un récepteur", () => {
    const display = buildDisplayGraph(graph, { scope: null, mode: "progressive" });
    expect(display.edges.some((edge) => edge.target.startsWith("load:"))).toBe(false);
    expect(display.edges.some((edge) => edge.source === "board:TGBT-01" && edge.target === "load:REC-01")).toBe(false);
  });

  it("affiche les départs directs en vue tableau sans les récepteurs", () => {
    const display = buildDisplayGraph(graph, {
      scope: { kind: "board", id: "TGBT-01" },
      mode: "progressive",
    });
    expect(display.nodes.map((node) => node.id).sort()).toEqual([
      "board:TGBT-01",
      "feeder:DEP-01",
      "feeder:DEP-02",
    ]);
    expect(display.nodes.some((node) => node.kind === "load")).toBe(false);
    expect(display.edges).toHaveLength(2);
  });

  it("affiche les récepteurs et le tableau amont en vue départ", () => {
    const display = buildDisplayGraph(graph, {
      scope: { kind: "feeder", id: "DEP-01" },
      mode: "progressive",
    });
    expect(display.nodes.map((node) => node.id).sort()).toEqual([
      "board:TGBT-01",
      "feeder:DEP-01",
      "load:REC-01",
      "load:REC-02",
    ]);
    expect(display.nodes.some((node) => node.id === "feeder:DEP-02")).toBe(false);
  });

  it("conserve le graphe complet en mode détaillé", () => {
    const display = buildDisplayGraph(graph, { scope: null, mode: "full" });
    expect(display.nodes).toHaveLength(graph.nodes.length);
    expect(display.edges).toHaveLength(graph.edges.length);
  });

  it("agrège les départs d'un tableau dense et les développe à la demande", () => {
    const feeders = Array.from({ length: 45 }, (_, index) => ({
      ...project.feeders[0],
      id: `DEP-LARGE-${index}`,
      designation: `Départ ${index}`,
      member_count: 1,
    }));
    const loads = feeders.map((item, index) => ({
      ...project.loads[0],
      id: `REC-LARGE-${index}`,
      feeder_id: item.id,
      designation: `Récepteur ${index}`,
    }));
    const large = {
      ...project,
      boards: [{ ...project.boards[0], feeder_count: feeders.length, load_count: loads.length }],
      feeders,
      loads,
      project: { ...project.project, feeder_count: feeders.length, load_count: loads.length },
    };
    const largeGraph = buildElectricalGraph(large);
    const collapsed = buildDisplayGraph(largeGraph, {
      scope: { kind: "board", id: "TGBT-01" },
      mode: "progressive",
    });
    expect(collapsed.nodes).toHaveLength(2);
    expect(collapsed.nodes.find((node) => node.aggregate)?.aggregate).toMatchObject({
      targetKind: "board-feeders",
      feederCount: 45,
      loadCount: 45,
    });
    const expanded = buildDisplayGraph(largeGraph, {
      scope: { kind: "board", id: "TGBT-01" },
      mode: "progressive",
      showBoardFeeders: true,
    });
    expect(expanded.nodes).toHaveLength(46);
    expect(expanded.nodes.filter((node) => node.kind === "feeder")).toHaveLength(45);
    expect(expanded.nodes.some((node) => node.kind === "aggregate")).toBe(false);
  });
});
