import { describe, expect, it } from "vitest";
import { buildElectricalGraph } from "../data/electricalGraph";
import { layoutElectricalGraph } from "../data/electricalGraphLayout";
import { board, feeder, load, project } from "./fixtures";
import type { FeederSummary, LoadSummary, ProjectPayload } from "../types";

function syntheticProject(count: number): ProjectPayload {
  const feeders: FeederSummary[] = [];
  const loads: LoadSummary[] = [];
  for (let index = 0; index < count; index += 1) {
    const suffix = String(index + 1).padStart(4, "0");
    const feederId = `PERF-DEP-${suffix}`;
    feeders.push({
      ...feeder,
      id: feederId,
      designation: `Départ ${suffix}`,
      member_count: 1,
      downstream_board_id: null,
    });
    loads.push({
      ...load,
      id: `PERF-REC-${suffix}`,
      designation: `Récepteur ${suffix}`,
      feeder_id: feederId,
      parent_board_id: "TGBT-01",
    });
  }
  return {
    ...project,
    project: { ...project.project, load_count: count, feeder_count: count, board_count: 1 },
    boards: [{ ...board, feeder_count: count, load_count: count }],
    feeders,
    loads,
    coherence: { ...project.coherence, unassigned_load_ids: [] },
  };
}

describe("layout graphique — volumes synthétiques", () => {
  it.each([30, 200, 1000])("mesure projection et layout pour %i récepteurs", (count) => {
    const input = syntheticProject(count);
    const projectionSamples: number[] = [];
    const layoutSamples: number[] = [];
    let graph = buildElectricalGraph(input);
    for (let run = 0; run < 5; run += 1) {
      const projectionStart = performance.now();
      graph = buildElectricalGraph(input);
      projectionSamples.push(performance.now() - projectionStart);
      const layoutStart = performance.now();
      layoutElectricalGraph(graph);
      layoutSamples.push(performance.now() - layoutStart);
    }
    const median = (values: number[]) => [...values].sort((a, b) => a - b)[2];
    expect(layoutSamples).toHaveLength(5);
    expect(graph.nodes).toHaveLength(1 + count + count);
    expect(graph.edges).toHaveLength(count + count);
    console.info(JSON.stringify({
      receptors: count,
      nodes: graph.nodes.length,
      edges: graph.edges.length,
      projection_ms_median_5: Number(median(projectionSamples).toFixed(3)),
      layout_ms_median_5: Number(median(layoutSamples).toFixed(3)),
    }));
  });
});
