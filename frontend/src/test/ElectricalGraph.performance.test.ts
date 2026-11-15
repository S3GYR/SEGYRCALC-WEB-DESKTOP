import { describe, expect, it } from "vitest";
import { buildElectricalGraph } from "../data/electricalGraph";
import { board, feeder, load, project } from "./fixtures";
import type { FeederSummary, LoadSummary, ProjectPayload } from "../types";

function syntheticProject(count: number): ProjectPayload {
  const feeders: FeederSummary[] = [];
  const loads: LoadSummary[] = [];
  for (let index = 0; index < count; index += 1) {
    const suffix = String(index + 1).padStart(4, "0");
    const feederId = `DEP-${suffix}`;
    feeders.push({
      ...feeder,
      id: feederId,
      designation: `Départ ${suffix}`,
      member_count: 1,
      downstream_board_id: null,
    });
    loads.push({
      ...load,
      id: `REC-${suffix}`,
      designation: `Récepteur ${suffix}`,
      feeder_id: feederId,
      parent_board_id: "TGBT-01",
    });
  }
  return {
    ...project,
    project: {
      ...project.project,
      load_count: count,
      feeder_count: count,
      board_count: 1,
      unassigned_load_count: 0,
    },
    boards: [board],
    feeders,
    loads,
    coherence: { ...project.coherence, unassigned_load_ids: [] },
  };
}

describe("projection graphique — volumes synthétiques", () => {
  it.each([30, 200, 1000])("mesure la projection de %i récepteurs", (count) => {
    const input = syntheticProject(count);
    const before = JSON.stringify(input);
    const samples: number[] = [];
    let graph = buildElectricalGraph(input);
    for (let run = 0; run < 5; run += 1) {
      const started = performance.now();
      graph = buildElectricalGraph(input);
      samples.push(performance.now() - started);
    }
    const sorted = [...samples].sort((left, right) => left - right);
    const median = sorted[Math.floor(sorted.length / 2)];
    const second = buildElectricalGraph(input);
    expect(graph).toEqual(second);
    expect(JSON.stringify(input)).toBe(before);
    expect(graph.nodes).toHaveLength(1 + count + count);
    expect(graph.edges).toHaveLength(count + count);
    console.info(JSON.stringify({
      receptors: count,
      nodes: graph.nodes.length,
      edges: graph.edges.length,
      milliseconds_median_5: Number(median.toFixed(3)),
      milliseconds_samples: samples.map((value) => Number(value.toFixed(3))),
      stable: true,
    }));
  });
});
