import { describe, expect, it } from "vitest";
import { buildElectricalGraph } from "../data/electricalGraph";
import { board, feeder, load, project } from "./fixtures";
import type { BoardSummary, FeederSummary, LoadSummary, ProjectPayload } from "../types";

function cloneProject(overrides: Partial<ProjectPayload> = {}): ProjectPayload {
  return {
    ...project,
    ...overrides,
    project: { ...project.project, ...(overrides.project ?? {}) },
    coherence: { ...project.coherence, ...(overrides.coherence ?? {}) },
  };
}

const board2: BoardSummary = {
  ...board,
  id: "TD-02",
  designation: "Tableau divisionnaire atelier",
  type: "DIVISIONNAIRE",
  parent_feeder_id: "DEP-02",
  feeder_count: 1,
  load_count: 1,
};

const feeder2: FeederSummary = {
  ...feeder,
  id: "DEP-02",
  designation: "Alimentation atelier",
  downstream_board_id: "TD-02",
  member_count: 0,
  ks: null,
};

const feeder3: FeederSummary = {
  ...feeder,
  id: "DEP-03",
  designation: "Départ terminal TD-02",
  parent_board_id: "TD-02",
  downstream_board_id: null,
  member_count: 1,
  ks: "0.9",
};

const load3: LoadSummary = {
  ...load,
  id: "REC-03",
  designation: "Récepteur TD-02",
  feeder_id: "DEP-03",
  parent_board_id: "TD-02",
};

const unassignedLoad: LoadSummary = {
  ...load,
  id: "REC-N1",
  designation: "Récepteur non affecté",
  feeder_id: "",
  parent_board_id: "",
};

describe("projection graphique électrique", () => {
  it("projette un projet minimal sans inventer de connexion", () => {
    const graph = buildElectricalGraph(cloneProject({
      feeders: [],
      loads: [],
      coherence: { ...project.coherence, unassigned_load_ids: [] },
      project: { ...project.project, feeder_count: 0, load_count: 0, unassigned_load_count: 0 },
    }));
    expect(graph.nodes).toHaveLength(1);
    expect(graph.nodes[0].id).toBe("board:TGBT-01");
    expect(graph.edges).toHaveLength(0);
    expect(graph.diagnostics.some((item) => item.code === "EMPTY_BOARD")).toBe(true);
  });

  it("projette le TGBT, les départs et les récepteurs avec des arêtes réelles", () => {
    const graph = buildElectricalGraph(project);
    expect(graph.nodes.map((node) => node.kind)).toEqual(
      expect.arrayContaining(["board", "feeder", "load"]),
    );
    expect(graph.edges.some((edge) => edge.id === "edge:board:TGBT-01->feeder:DEP-01")).toBe(true);
    expect(graph.edges.some((edge) => edge.id === "edge:feeder:DEP-01->load:REC-01")).toBe(true);
    expect(graph.edges.some((edge) => edge.kind === "feeder-to-board")).toBe(false);
    expect(graph.nodes.every((node) => ["board", "feeder", "load", "unassigned-group"].includes(node.kind))).toBe(true);
  });

  it("projette plusieurs tableaux divisionnaires et plusieurs niveaux", () => {
    const graph = buildElectricalGraph(cloneProject({
      boards: [board, board2],
      feeders: [feeder, feeder2, feeder3],
      loads: [load, load3],
    }));
    expect(graph.nodes.some((node) => node.id === "board:TD-02")).toBe(true);
    expect(graph.edges.some((edge) => edge.kind === "feeder-to-board")).toBe(true);
    expect(graph.edges.some((edge) => edge.id === "edge:feeder:DEP-03->load:REC-03")).toBe(true);
    expect(graph.diagnostics.some((item) => item.code === "CYCLE_DETECTED")).toBe(false);
  });

  it("signale un départ vide sans créer de faux récepteur", () => {
    const graph = buildElectricalGraph(cloneProject({
      feeders: [{ ...feeder, id: "DEP-EMPTY", member_count: 0 }],
      loads: [],
    }));
    expect(graph.nodes.filter((node) => node.kind === "load")).toHaveLength(0);
    expect(graph.diagnostics.some((item) => item.code === "EMPTY_FEEDER")).toBe(true);
  });

  it("projette les récepteurs non affectés dans un groupe sans arête électrique", () => {
    const graph = buildElectricalGraph(cloneProject({
      unassigned_loads: [unassignedLoad],
      coherence: { ...project.coherence, unassigned_load_ids: ["REC-N1"] },
      project: { ...project.project, unassigned_load_count: 1 },
    }));
    const group = graph.nodes.find((node) => node.kind === "unassigned-group");
    const unassigned = graph.nodes.find((node) => node.id === "load:REC-N1");
    expect(group?.selectable).toBe(false);
    expect(unassigned?.groupId).toBe("unassigned");
    expect(graph.edges.some((edge) => edge.target === "load:REC-N1")).toBe(false);
  });

  it("signale des non affectés annoncés sans détail disponible", () => {
    const graph = buildElectricalGraph(cloneProject({
      coherence: { ...project.coherence, unassigned_load_ids: ["REC-X1", "REC-X2", "REC-X3"] },
      project: { ...project.project, unassigned_load_count: 3 },
    }));
    expect(graph.nodes.some((node) => node.kind === "unassigned-group")).toBe(true);
    expect(graph.nodes.filter((node) => node.kind === "load" && node.groupId)).toHaveLength(0);
    expect(graph.diagnostics.some((item) => item.code === "UNASSIGNED_LOAD_DETAILS_UNAVAILABLE")).toBe(true);
  });

  it("rend les identifiants graphiques uniques entre types d'entités", () => {
    const sameId = "ENTITY-X";
    const graph = buildElectricalGraph(cloneProject({
      boards: [{ ...board, id: sameId, parent_feeder_id: null }],
      feeders: [{ ...feeder, id: sameId, parent_board_id: sameId, downstream_board_id: null, member_count: 1 }],
      loads: [{ ...load, id: sameId, feeder_id: sameId, parent_board_id: sameId }],
    }));
    const ids = graph.nodes.map((node) => node.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids).toEqual(expect.arrayContaining([
      `board:${sameId}`,
      `feeder:${sameId}`,
      `load:${sameId}`,
    ]));
  });

  it("est déterministe et ne mute pas l'entrée", () => {
    const input = cloneProject();
    const before = JSON.stringify(input);
    const first = buildElectricalGraph(input);
    const second = buildElectricalGraph(input);
    expect(first).toEqual(second);
    expect(JSON.stringify(input)).toBe(before);
  });

  it("n'expose aucun nœud source, transformateur ou secours fictif", () => {
    const graph = buildElectricalGraph(project);
    expect(graph.nodes.every((node) => ["board", "feeder", "load", "unassigned-group"].includes(node.kind))).toBe(true);
    expect(graph.edges.every((edge) => ["board-to-feeder", "feeder-to-board", "feeder-to-load"].includes(edge.kind))).toBe(true);
  });

  it("signale un cycle présent dans les données sans le réparer", () => {
    const graph = buildElectricalGraph(cloneProject({
      boards: [
        { ...board, id: "TGBT-01", parent_feeder_id: null },
        { ...board2, id: "TD-CYCLE", parent_feeder_id: "DEP-CYCLE" },
      ],
      feeders: [
        { ...feeder, id: "DEP-CYCLE", parent_board_id: "TGBT-01", downstream_board_id: "TD-CYCLE", member_count: 0 },
        { ...feeder3, id: "DEP-BACK", parent_board_id: "TD-CYCLE", downstream_board_id: "TGBT-01", member_count: 0 },
      ],
      loads: [],
    }));
    expect(graph.diagnostics.some((item) => item.code === "CYCLE_DETECTED")).toBe(true);
    expect(graph.edges.some((edge) => edge.kind === "feeder-to-board")).toBe(true);
  });

  it("signale les parents et tableaux aval absents", () => {
    const graph = buildElectricalGraph(cloneProject({
      boards: [board],
      feeders: [
        { ...feeder, id: "DEP-NO-PARENT", parent_board_id: "MISSING-BOARD", member_count: 0 },
        { ...feeder, id: "DEP-NO-CHILD", parent_board_id: "TGBT-01", downstream_board_id: "MISSING-BOARD", member_count: 0 },
      ],
      loads: [],
    }));
    expect(graph.diagnostics.some((item) => item.code === "FEEDER_PARENT_MISSING")).toBe(true);
    expect(graph.diagnostics.some((item) => item.code === "DOWNSTREAM_BOARD_MISSING")).toBe(true);
  });

  it("signale un compteur de membres incohérent", () => {
    const graph = buildElectricalGraph(project);
    expect(graph.diagnostics.some((item) => item.code === "MEMBER_COUNT_MISMATCH")).toBe(true);
  });

  it("copie les résultats moteur sans effectuer de calcul", () => {
    const graph = buildElectricalGraph(project);
    const tgbt = graph.nodes.find((node) => node.id === "board:TGBT-01");
    const motor = graph.nodes.find((node) => node.id === "load:REC-01");
    expect(tgbt?.metrics.p_after_ks_w).toBe(board.p_after_ks_w);
    expect(motor?.metrics.p_after_ks_w).toBe(load.p_after_ks_w);
    expect(motor?.metrics.current_a).toBe(load.current_a);
  });

  it("conserve les identifiants métier dans entityId", () => {
    const graph = buildElectricalGraph(project);
    expect(graph.nodes.find((node) => node.id === "board:TGBT-01")?.entityId).toBe("TGBT-01");
    expect(graph.nodes.find((node) => node.id === "feeder:DEP-01")?.entityId).toBe("DEP-01");
    expect(graph.nodes.find((node) => node.id === "load:REC-01")?.entityId).toBe("REC-01");
  });

  it("est compatible avec un projet sans aucun tableau", () => {
    const graph = buildElectricalGraph(cloneProject({
      boards: [],
      feeders: [],
      loads: [],
      project: { ...project.project, board_count: 0, feeder_count: 0, load_count: 0, unassigned_load_count: 0 },
    }));
    expect(graph.nodes).toHaveLength(0);
    expect(graph.diagnostics.some((item) => item.code === "NO_BOARD")).toBe(true);
  });
});
