import type { ElectricalGraph, ElectricalGraphNode } from "./electricalGraph";

export type GraphScope =
  | { kind: "board"; id: string }
  | { kind: "feeder"; id: string }
  | null;

export type GraphScopeState = {
  scope: GraphScope;
  history: GraphScope[];
};

export function nodeById(graph: ElectricalGraph): Map<string, ElectricalGraphNode> {
  return new Map(graph.nodes.map((node) => [node.id, node]));
}

export function incomingParentMap(graph: ElectricalGraph): Map<string, string> {
  const parent = new Map<string, string>();
  for (const edge of graph.edges) {
    if (!parent.has(edge.target)) parent.set(edge.target, edge.source);
  }
  return parent;
}

function outgoingMap(graph: ElectricalGraph): Map<string, string[]> {
  const outgoing = new Map<string, string[]>();
  for (const node of graph.nodes) outgoing.set(node.id, []);
  for (const edge of graph.edges) {
    if (outgoing.has(edge.source) && outgoing.has(edge.target)) {
      outgoing.get(edge.source)!.push(edge.target);
    }
  }
  return outgoing;
}

/**
 * Presentation-only descendant index. It follows real graph edges and never
 * creates a relation that is absent from the project projection.
 */
export function descendantMap(graph: ElectricalGraph): Map<string, Set<string>> {
  const children = outgoingMap(graph);
  const result = new Map<string, Set<string>>();
  for (const node of graph.nodes) {
    const descendants = new Set<string>();
    const stack = [...(children.get(node.id) ?? [])];
    while (stack.length > 0) {
      const current = stack.pop()!;
      if (current === node.id || descendants.has(current)) continue;
      descendants.add(current);
      stack.push(...(children.get(current) ?? []));
    }
    result.set(node.id, descendants);
  }
  return result;
}

/**
 * Returns the ancestor path from the electrical root to the requested node,
 * including the node itself. It only walks existing graph edges.
 */
export function pathToNode(graph: ElectricalGraph, nodeId: string): ElectricalGraphNode[] {
  const nodes = nodeById(graph);
  const parent = incomingParentMap(graph);
  const chain: string[] = [];
  const seen = new Set<string>();
  let current: string | undefined = nodeId;
  while (current) {
    if (seen.has(current)) break;
    seen.add(current);
    const node = nodes.get(current);
    if (!node) break;
    chain.unshift(current);
    current = parent.get(current);
  }
  return chain.map((id) => nodes.get(id)).filter((node): node is ElectricalGraphNode => Boolean(node));
}

export function scopePath(graph: ElectricalGraph, scope: GraphScope): ElectricalGraphNode[] {
  if (!scope) return [];
  return pathToNode(graph, `${scope.kind}:${scope.id}`);
}

/**
 * Includes the selected scope, its upstream path and all descendants. The
 * upstream path keeps the relation to the source/TGBT identifiable.
 */
export function scopeNodeIds(graph: ElectricalGraph, scope: GraphScope): Set<string> {
  if (!scope) return new Set(graph.nodes.map((node) => node.id));
  const descendants = descendantMap(graph);
  const scopeId = `${scope.kind}:${scope.id}`;
  const nodes = new Set<string>();
  for (const node of pathToNode(graph, scopeId)) nodes.add(node.id);
  nodes.add(scopeId);
  for (const id of descendants.get(scopeId) ?? []) nodes.add(id);
  return nodes;
}

export function collapsedDescendantIds(
  graph: ElectricalGraph,
  collapsed: ReadonlySet<string>,
): Set<string> {
  const descendants = descendantMap(graph);
  const hidden = new Set<string>();
  for (const id of collapsed) {
    for (const child of descendants.get(id) ?? []) hidden.add(child);
  }
  return hidden;
}

export function visibleNodeIds(
  graph: ElectricalGraph,
  scope: GraphScope,
  collapsed: ReadonlySet<string>,
): Set<string> {
  const scoped = scopeNodeIds(graph, scope);
  const hidden = collapsedDescendantIds(graph, collapsed);
  return new Set([...scoped].filter((id) => !hidden.has(id)));
}

export function hiddenCount(
  graph: ElectricalGraph,
  nodeId: string,
): number {
  return descendantMap(graph).get(nodeId)?.size ?? 0;
}

export function ancestorsForNode(graph: ElectricalGraph, nodeId: string): string[] {
  return pathToNode(graph, nodeId).slice(0, -1).map((node) => node.id);
}

export function visibleEdgeIds(
  graph: ElectricalGraph,
  visibleIds: ReadonlySet<string>,
): Set<string> {
  return new Set(
    graph.edges
      .filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target))
      .map((edge) => edge.id),
  );
}
