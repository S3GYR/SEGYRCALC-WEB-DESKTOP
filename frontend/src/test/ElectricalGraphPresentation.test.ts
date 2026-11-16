import { describe, expect, it } from "vitest";
import { buildElectricalGraph } from "../data/electricalGraph";
import {
  ancestorsForNode,
  descendantMap,
  pathToNode,
  scopeNodeIds,
  scopePath,
  visibleEdgeIds,
  visibleNodeIds,
} from "../data/electricalGraphPresentation";
import { project } from "./fixtures";

describe("présentation graphique: périmètre, repli et navigation", () => {
  const graph = buildElectricalGraph(project);

  it("construit un chemin réel depuis la racine jusqu'au récepteur", () => {
    const path = pathToNode(graph, "load:REC-01");
    expect(path.map((node) => node.id)).toEqual([
      "board:TGBT-01",
      "feeder:DEP-01",
      "load:REC-01",
    ]);
    expect(scopePath(graph, { kind: "feeder", id: "DEP-02" }).map((node) => node.id)).toEqual([
      "board:TGBT-01",
      "feeder:DEP-02",
    ]);
  });

  it("inclut le tableau et ses descendants dans le périmètre tableau", () => {
    const ids = scopeNodeIds(graph, { kind: "board", id: "TGBT-01" });
    expect(ids.has("board:TGBT-01")).toBe(true);
    expect(ids.has("feeder:DEP-01")).toBe(true);
    expect(ids.has("feeder:DEP-02")).toBe(true);
    expect(ids.has("load:REC-01")).toBe(true);
  });

  it("inclut les descendants et les ancêtres d'un départ", () => {
    const ids = scopeNodeIds(graph, { kind: "feeder", id: "DEP-01" });
    expect(ids.has("board:TGBT-01")).toBe(true);
    expect(ids.has("feeder:DEP-01")).toBe(true);
    expect(ids.has("load:REC-01")).toBe(true);
    expect(ids.has("feeder:DEP-02")).toBe(false);
  });

  it("masque tous les descendants d'une branche repliée", () => {
    const hidden = descendantMap(graph).get("board:TGBT-01");
    expect(hidden?.has("feeder:DEP-02")).toBe(true);
    expect(hidden?.has("load:REC-01")).toBe(true);
    const visible = visibleNodeIds(graph, null, new Set(["board:TGBT-01"]));
    expect(visible.has("board:TGBT-01")).toBe(true);
    expect(visible.has("feeder:DEP-02")).toBe(false);
    expect(visible.has("load:REC-01")).toBe(false);
  });

  it("conserve les arêtes uniquement si leurs deux extrémités sont visibles", () => {
    const visible = visibleNodeIds(graph, null, new Set(["feeder:DEP-01"]));
    const edges = visibleEdgeIds(graph, visible);
    expect(edges.has("edge:board:TGBT-01->feeder:DEP-01")).toBe(true);
    expect(edges.has("edge:feeder:DEP-01->load:REC-01")).toBe(false);
  });

  it("retourne les ancêtres d'un récepteur pour révéler sa branche", () => {
    expect(ancestorsForNode(graph, "load:REC-01")).toEqual([
      "board:TGBT-01",
      "feeder:DEP-01",
    ]);
  });

  it("ne mute pas le graphe", () => {
    const before = JSON.stringify(graph);
    scopeNodeIds(graph, { kind: "board", id: "TGBT-01" });
    visibleNodeIds(graph, null, new Set(["board:TGBT-01"]));
    expect(JSON.stringify(graph)).toBe(before);
  });
});
