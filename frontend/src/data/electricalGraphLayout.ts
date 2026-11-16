export type ElectricalGraphPoint = { x: number; y: number };

export type ElectricalGraphLayout = {
  positions: Record<string, ElectricalGraphPoint>;
  levels: Record<string, number>;
  maxLevel: number;
  rowsByLevel: Record<number, number>;
  columnsByLevel: Record<number, number>;
  width: number;
  height: number;
};

export const GRAPH_NODE_WIDTH = 250;
export const GRAPH_NODE_HEIGHT = 120;
export const GRAPH_ROW_HEIGHT = 150;
export const GRAPH_LEVEL_GAP = 48;

export type LayoutGraphNode = { id: string; kind: string };
export type LayoutGraphEdge = { source: string; target: string };
export type LayoutGraph = { nodes: LayoutGraphNode[]; edges: LayoutGraphEdge[] };
export type GraphViewport = { x: number; y: number; zoom: number };
export type GraphBounds = { minX: number; minY: number; maxX: number; maxY: number };

function groupOrder(graph: LayoutGraph): Map<string, string> {
  const index = new Map(graph.nodes.map((node, order) => [node.id, order]));
  const incoming = new Map<string, string>();
  for (const edge of graph.edges) {
    if (!incoming.has(edge.target) && index.has(edge.source)) {
      incoming.set(edge.target, edge.source);
    }
  }
  return incoming;
}

function columnsFor(count: number): number {
  if (count <= 1) return 1;
  // A near-square grid avoids the runaway horizontal band of the old layout
  // while keeping the deterministic, dependency-free implementation.
  return Math.max(1, Math.min(count, Math.ceil(Math.sqrt(count * 1.35))));
}

/**
 * Deterministic layered layout with wrapped rows.
 *
 * Nodes are still assigned electrical levels by breadth-first traversal of the
 * real graph. Within a level, children are ordered by their first known parent
 * and then by projection order. Rows are wrapped with a dynamic column count;
 * positions therefore do not depend on the viewport or on user interaction.
 */
export function layoutElectricalGraph(graph: LayoutGraph): ElectricalGraphLayout {
  const nodes = graph.nodes;
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const incoming = new Map<string, string[]>();
  const outgoing = new Map<string, string[]>();
  for (const node of nodes) {
    incoming.set(node.id, []);
    outgoing.set(node.id, []);
  }
  for (const edge of graph.edges) {
    if (!byId.has(edge.source) || !byId.has(edge.target)) continue;
    incoming.get(edge.target)!.push(edge.source);
    outgoing.get(edge.source)!.push(edge.target);
  }

  const levels = new Map<string, number>();
  const sourceRoots = nodes
    .filter((node) => node.kind === "source" && (incoming.get(node.id)?.length ?? 0) === 0)
    .map((node) => node.id);
  const boardRoots = nodes
    .filter((node) => node.kind === "board" && (incoming.get(node.id)?.length ?? 0) === 0)
    .map((node) => node.id);
  const firstBoard = nodes.find((node) => node.kind === "board");
  const roots = sourceRoots.length > 0
    ? sourceRoots
    : boardRoots.length > 0
      ? boardRoots
      : firstBoard
        ? [firstBoard.id]
        : [];

  const queue: Array<{ id: string; level: number }> = roots.map((id) => ({ id, level: 0 }));
  for (const root of roots) levels.set(root, 0);
  while (queue.length > 0) {
    const current = queue.shift()!;
    for (const target of outgoing.get(current.id) ?? []) {
      if (levels.has(target)) continue;
      const nextLevel = current.level + 1;
      levels.set(target, nextLevel);
      queue.push({ id: target, level: nextLevel });
    }
  }

  let maxLevel = levels.size > 0 ? Math.max(...levels.values()) : -1;
  for (const node of nodes) {
    if (!levels.has(node.id)) {
      const level = maxLevel + 1;
      levels.set(node.id, level);
      maxLevel = Math.max(maxLevel, level);
    }
  }

  const parentOrder = groupOrder(graph);
  const order = new Map(nodes.map((node, index) => [node.id, index]));
  const byLevel = new Map<number, LayoutGraphNode[]>();
  for (const node of nodes) {
    const level = levels.get(node.id) ?? 0;
    const list = byLevel.get(level) ?? [];
    list.push(node);
    byLevel.set(level, list);
  }
  for (const list of byLevel.values()) {
    list.sort((left, right) => {
      const leftParent = parentOrder.get(left.id);
      const rightParent = parentOrder.get(right.id);
      const parentDelta =
        (leftParent ? order.get(leftParent) ?? 0 : Number.MAX_SAFE_INTEGER) -
        (rightParent ? order.get(rightParent) ?? 0 : Number.MAX_SAFE_INTEGER);
      if (parentDelta !== 0) return parentDelta;
      return (order.get(left.id) ?? 0) - (order.get(right.id) ?? 0);
    });
  }

  const positions: Record<string, ElectricalGraphPoint> = {};
  const rowsByLevel: Record<number, number> = {};
  const columnsByLevel: Record<number, number> = {};
  let y = 0;
  let maxWidth = 0;
  for (const level of [...byLevel.keys()].sort((a, b) => a - b)) {
    const list = byLevel.get(level) ?? [];
    const columns = columnsFor(list.length);
    const rows = Math.ceil(list.length / columns);
    columnsByLevel[level] = columns;
    rowsByLevel[level] = rows;
    maxWidth = Math.max(maxWidth, columns * GRAPH_NODE_WIDTH);
    list.forEach((node, index) => {
      const row = Math.floor(index / columns);
      const column = index % columns;
      positions[node.id] = {
        x: column * GRAPH_NODE_WIDTH,
        y: y + row * GRAPH_ROW_HEIGHT,
      };
    });
    y += rows * GRAPH_ROW_HEIGHT + GRAPH_LEVEL_GAP;
  }

  return {
    positions,
    levels: Object.fromEntries(levels),
    maxLevel,
    rowsByLevel,
    columnsByLevel,
    width: nodes.length === 0 ? 0 : maxWidth,
    height: nodes.length === 0 ? 0 : Math.max(0, y - GRAPH_LEVEL_GAP),
  };
}

/** Bounds are derived from deterministic layout positions, not DOM measurements. */
export function layoutBounds(
  layout: ElectricalGraphLayout,
  nodeIds: ReadonlySet<string>,
  nodeWidth = GRAPH_NODE_WIDTH,
  nodeHeight = GRAPH_NODE_HEIGHT,
): GraphBounds | null {
  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;
  let found = false;
  for (const id of nodeIds) {
    const point = layout.positions[id];
    if (!point) continue;
    found = true;
    minX = Math.min(minX, point.x);
    minY = Math.min(minY, point.y);
    maxX = Math.max(maxX, point.x + nodeWidth);
    maxY = Math.max(maxY, point.y + nodeHeight);
  }
  return found ? { minX, minY, maxX, maxY } : null;
}

/** Compute a viewport from layout bounds without React Flow measuring every node. */
export function computeFitViewport(
  bounds: GraphBounds,
  viewportWidth: number,
  viewportHeight: number,
  padding = 0.18,
  minZoom = 0.1,
  maxZoom = 1.2,
): GraphViewport | null {
  if (viewportWidth <= 0 || viewportHeight <= 0) return null;
  const contentWidth = Math.max(1, bounds.maxX - bounds.minX);
  const contentHeight = Math.max(1, bounds.maxY - bounds.minY);
  const availableWidth = Math.max(1, viewportWidth * (1 - 2 * padding));
  const availableHeight = Math.max(1, viewportHeight * (1 - 2 * padding));
  const zoom = Math.max(
    minZoom,
    Math.min(maxZoom, availableWidth / contentWidth, availableHeight / contentHeight),
  );
  return {
    x: viewportWidth / 2 - ((bounds.minX + bounds.maxX) / 2) * zoom,
    y: viewportHeight / 2 - ((bounds.minY + bounds.maxY) / 2) * zoom,
    zoom,
  };
}
