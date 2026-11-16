import type {
  ElectricalGraph,
  ElectricalGraphEdge,
  ElectricalGraphEdgeKind,
  ElectricalGraphNode,
  ElectricalGraphNodeKind,
} from "./electricalGraph";
import { pathToNode, scopeNodeIds, type GraphScope } from "./electricalGraphPresentation";
import type { SourcePayload } from "../types";

/**
 * Presentation-only graph used by the React Flow renderer.
 *
 * The business graph is never mutated. Aggregated nodes and edges are derived
 * from real graph paths so counts remain traceable and no electrical relation
 * is invented.
 */

export type DisplayNodeKind = ElectricalGraphNodeKind | "aggregate" | "source";
export type GraphDisplayMode = "progressive" | "full";

export type AggregateNodeInfo = {
  role: "board-branches" | "board-feeders";
  parentNodeId: string;
  parentLabel: string;
  feederCount: number;
  loadCount: number;
  hiddenNodeIds: string[];
  targetKind: "board" | "board-feeders";
  targetId: string;
};

export type DisplayNode = Omit<ElectricalGraphNode, "kind"> & {
  kind: DisplayNodeKind;
  aggregate?: AggregateNodeInfo;
};

export type DisplayEdgeKind = ElectricalGraphEdgeKind | "aggregated" | "source-to-board";

export type DisplayEdge = Omit<ElectricalGraphEdge, "kind"> & {
  kind: DisplayEdgeKind;
  aggregated?: {
    viaNodeIds: string[];
    originalEdgeIds: string[];
    label: string;
  };
};

export type DisplayGraph = {
  nodes: DisplayNode[];
  edges: DisplayEdge[];
  hiddenRealNodeIds: Set<string>;
  aggregateCount: number;
};

export type DisplayGraphOptions = {
  scope: GraphScope;
  mode: GraphDisplayMode;
  source?: SourcePayload | null;
  showBoardFeeders?: boolean;
};

const BOARD_FEEDER_AGGREGATE_THRESHOLD = 40;

function emptyMetrics() {
  return {
    p_installed_w: null,
    p_after_ku_w: null,
    p_after_ks_w: null,
    q_after_ks_var: null,
    s_after_ks_va: null,
    current_a: null,
    neutral_current_a: null,
    unbalance_percent: null,
  };
}

function toDisplayNode(node: ElectricalGraphNode): DisplayNode {
  return { ...node };
}

export function isRealNodeKind(kind: DisplayNodeKind): kind is ElectricalGraphNodeKind {
  return kind === "board" || kind === "feeder" || kind === "load" || kind === "unassigned-group";
}

function realIds(graph: ElectricalGraph): Set<string> {
  return new Set(graph.nodes.map((node) => node.id));
}

function subsetGraph(
  graph: ElectricalGraph,
  ids: ReadonlySet<string>,
  aggregateCount = 0,
): DisplayGraph {
  const nodes = graph.nodes.filter((node) => ids.has(node.id)).map(toDisplayNode);
  const edges = graph.edges
    .filter((edge) => ids.has(edge.source) && ids.has(edge.target))
    .map((edge) => ({ ...edge }));
  const hiddenRealNodeIds = new Set(
    graph.nodes.filter((node) => !ids.has(node.id)).map((node) => node.id),
  );
  return { nodes, edges, hiddenRealNodeIds, aggregateCount };
}

function sourceDisplayNode(source: SourcePayload): DisplayNode {
  const label = source.designation || source.reference || source.id;
  const nominal = source.rated_power
    ? ` · ${source.rated_power} ${source.rated_power_unit}`
    : "";
  return {
    id: `source:${source.id}`,
    kind: "source",
    entityId: null,
    label,
    meta: `${source.source_type}${nominal}`,
    status: "OK",
    selectable: false,
    metrics: emptyMetrics(),
  };
}

function sourceRootEdges(graph: ElectricalGraph, source: SourcePayload): DisplayEdge[] {
  const roots = graph.nodes.filter(
    (node) => node.kind === "board" && !graph.edges.some((edge) => edge.target === node.id),
  );
  return roots.map((board) => ({
    id: `aggregate:source:${source.id}->${board.id}`,
    kind: "source-to-board",
    source: `source:${source.id}`,
    target: board.id,
    feederId: "",
    label: "Alimentation source",
    status: "OK",
  }));
}

function addSource(
  graph: ElectricalGraph,
  nodes: DisplayNode[],
  edges: DisplayEdge[],
  source?: SourcePayload | null,
): void {
  if (!source || graph.nodes.length === 0) return;
  nodes.push(sourceDisplayNode(source));
  edges.push(...sourceRootEdges(graph, source));
}

function boardBranchesAggregate(
  graph: ElectricalGraph,
  board: ElectricalGraphNode,
): DisplayNode | null {
  const feederEdges = graph.edges.filter(
    (edge) => edge.kind === "board-to-feeder" && edge.source === board.id,
  );
  const terminalFeeders: ElectricalGraphNode[] = [];
  const loadIds = new Set<string>();
  for (const edge of feederEdges) {
    const childBoard = graph.edges.some(
      (candidate) => candidate.kind === "feeder-to-board" && candidate.source === edge.target,
    );
    if (childBoard) continue;
    const feeder = graph.nodes.find((node) => node.id === edge.target);
    if (!feeder) continue;
    terminalFeeders.push(feeder);
    for (const loadEdge of graph.edges) {
      if (loadEdge.kind === "feeder-to-load" && loadEdge.source === feeder.id) {
        loadIds.add(loadEdge.target);
      }
    }
  }
  if (terminalFeeders.length === 0) return null;
  const parentReference = board.entityId ?? board.id;
  return {
    id: `aggregate:board-branches:${board.entityId ?? board.id}`,
    kind: "aggregate",
    entityId: null,
    label: "Branches terminales",
    meta: `Tableau ${parentReference} · ${terminalFeeders.length} départ(s) · ${loadIds.size} récepteur(s)`,
    status: "INFO",
    selectable: false,
    metrics: emptyMetrics(),
    aggregate: {
      role: "board-branches",
      parentNodeId: board.id,
      parentLabel: board.label,
      feederCount: terminalFeeders.length,
      loadCount: loadIds.size,
      hiddenNodeIds: [...terminalFeeders.map((feeder) => feeder.id), ...loadIds],
      targetKind: "board",
      targetId: board.entityId ?? "",
    },
  };
}

function installationOverview(
  graph: ElectricalGraph,
  source?: SourcePayload | null,
): DisplayGraph {
  const nodes: DisplayNode[] = [];
  const edges: DisplayEdge[] = [];
  const included = new Set<string>();
  const allReal = realIds(graph);

  for (const board of graph.nodes.filter((node) => node.kind === "board")) {
    nodes.push(toDisplayNode(board));
    included.add(board.id);
  }
  for (const group of graph.nodes.filter((node) => node.kind === "unassigned-group")) {
    nodes.push(toDisplayNode(group));
    included.add(group.id);
  }
  addSource(graph, nodes, edges, source);

  for (const board of graph.nodes.filter((node) => node.kind === "board")) {
    const boardEdges = graph.edges.filter(
      (edge) => edge.kind === "board-to-feeder" && edge.source === board.id,
    );
    const structural = new Map<string, { feeders: ElectricalGraphNode[]; original: string[] }>();
    for (const edge of boardEdges) {
      const feeder = graph.nodes.find((node) => node.id === edge.target);
      if (!feeder) continue;
      const downstreamEdges = graph.edges.filter(
        (candidate) => candidate.kind === "feeder-to-board" && candidate.source === feeder.id,
      );
      for (const downstream of downstreamEdges) {
        const existing = structural.get(downstream.target) ?? { feeders: [], original: [] };
        existing.feeders.push(feeder);
        existing.original.push(edge.id, downstream.id);
        structural.set(downstream.target, existing);
      }
    }
    for (const [childId, structuralPath] of structural.entries()) {
      included.add(childId);
      const labels = [...new Set(structuralPath.feeders.map((feeder) => feeder.label))];
      const via = labels.length > 2 ? `${labels.slice(0, 2).join(", ")} +${labels.length - 2}` : labels.join(", ");
      edges.push({
        id: `aggregate:board-path:${board.id}->${childId}`,
        kind: "aggregated",
        source: board.id,
        target: childId,
        feederId: structuralPath.feeders[0]?.entityId ?? "",
        label: via ? `via ${via}` : "Liaison agrégée",
        status: "OK",
        aggregated: {
          viaNodeIds: structuralPath.feeders.map((feeder) => feeder.id),
          originalEdgeIds: structuralPath.original,
          label: via ? `via ${via}` : "Liaison agrégée",
        },
      });
    }
    const aggregate = boardBranchesAggregate(graph, board);
    if (aggregate?.aggregate) {
      nodes.push(aggregate);
      included.add(aggregate.id);
      edges.push({
        id: `aggregate:board-branches-edge:${board.id}`,
        kind: "aggregated",
        source: board.id,
        target: aggregate.id,
        feederId: "",
        label: `${aggregate.aggregate.feederCount} départ(s)`,
        status: "INFO",
        aggregated: {
          viaNodeIds: aggregate.aggregate.hiddenNodeIds.filter((id) => id.startsWith("feeder:")),
          originalEdgeIds: (() => {
            const terminalIds = new Set(
              aggregate.aggregate!.hiddenNodeIds.filter((id) => id.startsWith("feeder:")),
            );
            return graph.edges
              .filter(
                (edge) =>
                  edge.kind === "board-to-feeder" &&
                  edge.source === board.id &&
                  terminalIds.has(edge.target),
              )
              .map((edge) => edge.id);
          })(),
          label: `${aggregate.aggregate.feederCount} départ(s)`,
        },
      });
    }
  }

  const hiddenRealNodeIds = new Set([...allReal].filter((id) => !included.has(id)));
  return {
    nodes,
    edges,
    hiddenRealNodeIds,
    aggregateCount: nodes.filter((node) => node.kind === "aggregate").length,
  };
}

function boardView(
  graph: ElectricalGraph,
  boardId: string,
  showBoardFeeders = false,
): DisplayGraph {
  const boardNodeId = `board:${boardId}`;
  const path = pathToNode(graph, boardNodeId);
  const ids = new Set(path.map((node) => node.id));
  const board = graph.nodes.find((node) => node.id === boardNodeId);
  if (!board) return subsetGraph(graph, new Set());
  ids.add(board.id);
  const directFeeders = graph.edges.filter(
    (edge) => edge.kind === "board-to-feeder" && edge.source === board.id,
  );
  const terminalFeeders: ElectricalGraphNode[] = [];
  const terminalLoadIds = new Set<string>();
  for (const edge of directFeeders) {
    const downstream = graph.edges.filter(
      (candidate) => candidate.kind === "feeder-to-board" && candidate.source === edge.target,
    );
    if (downstream.length > 0) {
      for (const child of downstream) ids.add(child.target);
      continue;
    }
    const feeder = graph.nodes.find((node) => node.id === edge.target);
    if (feeder) terminalFeeders.push(feeder);
    for (const loadEdge of graph.edges) {
      if (loadEdge.kind === "feeder-to-load" && loadEdge.source === edge.target) {
        terminalLoadIds.add(loadEdge.target);
      }
    }
  }
  const aggregate: DisplayNode | null =
    !showBoardFeeders && terminalFeeders.length > BOARD_FEEDER_AGGREGATE_THRESHOLD
      ? {
          id: `aggregate:board-feeders:${board.entityId ?? board.id}`,
          kind: "aggregate",
          entityId: null,
          label: "Départs terminaux",
          meta: `Tableau ${board.entityId ?? board.id} · ${terminalFeeders.length} départ(s) · ${terminalLoadIds.size} récepteur(s)`,
          status: "INFO",
          selectable: false,
          metrics: emptyMetrics(),
          aggregate: {
            role: "board-feeders",
            parentNodeId: board.id,
            parentLabel: board.label,
            feederCount: terminalFeeders.length,
            loadCount: terminalLoadIds.size,
            hiddenNodeIds: [...terminalFeeders.map((feeder) => feeder.id), ...terminalLoadIds],
            targetKind: "board-feeders",
            targetId: board.entityId ?? "",
          },
        }
      : null;
  if (aggregate) {
    ids.add(aggregate.id);
  } else {
    for (const feeder of terminalFeeders) ids.add(feeder.id);
  }
  if (showBoardFeeders && terminalFeeders.length > 0) {
    for (const feeder of terminalFeeders) {
      for (const downstream of graph.edges) {
        if (downstream.kind === "feeder-to-board" && downstream.source === feeder.id) {
          ids.add(downstream.target);
        }
      }
    }
  }
  const result = subsetGraph(graph, ids);
  if (aggregate) {
    result.aggregateCount = 1;
    result.nodes.push(aggregate);
    result.edges.push({
      id: `aggregate:board-feeders-edge:${board.id}`,
      kind: "aggregated",
      source: board.id,
      target: aggregate.id,
      feederId: "",
      label: `${terminalFeeders.length} départ(s)`,
      status: "INFO",
      aggregated: {
        viaNodeIds: terminalFeeders.map((feeder) => feeder.id),
        originalEdgeIds: graph.edges
          .filter(
            (edge) =>
              edge.kind === "board-to-feeder" &&
              edge.source === board.id &&
              terminalFeeders.some((feeder) => feeder.id === edge.target),
          )
          .map((edge) => edge.id),
        label: `${terminalFeeders.length} départ(s)`,
      },
    });
  }
  return result;
}

function feederView(graph: ElectricalGraph, feederId: string): DisplayGraph {
  const feederNodeId = `feeder:${feederId}`;
  const path = pathToNode(graph, feederNodeId);
  const ids = new Set(path.map((node) => node.id));
  const feeder = graph.nodes.find((node) => node.id === feederNodeId);
  if (!feeder) return subsetGraph(graph, new Set());
  for (const edge of graph.edges) {
    if (edge.kind === "feeder-to-load" && edge.source === feeder.id) ids.add(edge.target);
    if (edge.kind === "feeder-to-board" && edge.source === feeder.id) ids.add(edge.target);
  }
  return subsetGraph(graph, ids);
}

function fullView(
  graph: ElectricalGraph,
  scope: GraphScope,
  source?: SourcePayload | null,
): DisplayGraph {
  const ids = scopeNodeIds(graph, scope);
  const result = subsetGraph(graph, ids);
  if (scope === null && source) {
    result.nodes.push(sourceDisplayNode(source));
    result.edges.push(...sourceRootEdges(graph, source));
  }
  return result;
}

/**
 * Build a display graph. Progressive mode is intentionally structural:
 * installation => boards + terminal branch aggregates; board => direct
 * feeders and downstream boards; feeder => direct loads.
 */
export function buildDisplayGraph(
  graph: ElectricalGraph,
  options: DisplayGraphOptions,
): DisplayGraph {
  if (options.mode === "full") {
    return fullView(graph, options.scope, options.source);
  }
  if (options.scope === null) {
    return installationOverview(graph, options.source);
  }
  if (options.scope.kind === "board") {
    return boardView(graph, options.scope.id, options.showBoardFeeders ?? false);
  }
  return feederView(graph, options.scope.id);
}
