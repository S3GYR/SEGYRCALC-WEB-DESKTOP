import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  buildElectricalGraph,
  type ElectricalGraphDiagnostic,
  type ElectricalGraphMetrics,
} from "../data/electricalGraph";
import {
  buildDisplayGraph,
  isRealNodeKind,
  type AggregateNodeInfo,
  type DisplayNodeKind,
  type GraphDisplayMode,
} from "../data/electricalGraphDisplay";
import {
  GRAPH_NODE_HEIGHT,
  GRAPH_NODE_WIDTH,
  computeFitViewport,
  layoutBounds,
  layoutElectricalGraph,
} from "../data/electricalGraphLayout";
import {
  ancestorsForNode,
  collapsedDescendantIds,
  descendantMap,
  pathToNode,
  scopeNodeIds,
  scopePath,
  type GraphScope,
} from "../data/electricalGraphPresentation";
import { formatApparentPower, formatCurrent, formatPower } from "../format";
import type { ProjectPayload, Selection } from "../types";

type ElectricalFlowData = {
  kind: DisplayNodeKind;
  entityId: string | null;
  nodeId: string;
  label: string;
  meta: string;
  status: string;
  metrics: ElectricalGraphMetrics;
  groupId?: string;
  collapsed: boolean;
  hiddenCount: number;
  hasChildren: boolean;
  onToggle: (nodeId: string) => void;
  aggregate?: AggregateNodeInfo;
  onOpenScope?: () => void;
};

type ElectricalFlowNode = Node<ElectricalFlowData, DisplayNodeKind>;

const nodeTypes = {
  board: ElectricalNode,
  feeder: ElectricalNode,
  load: ElectricalNode,
  "unassigned-group": ElectricalNode,
  aggregate: ElectricalNode,
  source: ElectricalNode,
};

function nodeSelection(data: ElectricalFlowData): Selection | null {
  if (!data.entityId) return null;
  if (data.kind === "board" || data.kind === "feeder" || data.kind === "load") {
    return { kind: data.kind, id: data.entityId };
  }
  return null;
}

function isSelected(data: ElectricalFlowData, selection: Selection | null): boolean {
  const candidate = nodeSelection(data);
  return Boolean(candidate && selection && candidate.kind === selection.kind && candidate.id === selection.id);
}

function nodeIcon(kind: DisplayNodeKind): string {
  if (kind === "board") return "▦";
  if (kind === "feeder") return "↳";
  if (kind === "load") return "●";
  if (kind === "aggregate") return "Σ";
  if (kind === "source") return "⚡";
  return "◇";
}

function kindLabel(kind: DisplayNodeKind): string {
  if (kind === "unassigned-group") return "NON AFFECTÉS";
  if (kind === "aggregate") return "BRANCHE AGRÉGÉE";
  if (kind === "source") return "SOURCE";
  return kind.toUpperCase();
}

function ElectricalNode({ data, selected }: NodeProps<ElectricalFlowNode>) {
  const isUnassigned = data.kind === "load" && data.groupId === "unassigned";
  const unavailable = data.kind === "load" && data.metrics.p_after_ku_w === null;
  const isPresentation = data.kind === "aggregate" || data.kind === "source";
  const toggle = () => {
    if (data.hasChildren) data.onToggle(data.nodeId);
  };
  return (
    <div
      className={`electrical-node electrical-node-${data.kind}${isUnassigned ? " is-unassigned" : ""}${selected ? " is-selected" : ""}${isPresentation ? " is-presentation" : ""}`}
      data-testid={`graph-node-${data.kind}-${data.entityId ?? (data.nodeId === "group:unassigned" ? "unassigned" : data.nodeId)}`}
      title={`${data.label} — ${data.meta}`}
    >
      {data.kind !== "unassigned-group" && (
        <>
          <Handle type="target" position={Position.Top} isConnectable={false} />
          <Handle type="source" position={Position.Bottom} isConnectable={false} />
        </>
      )}
      <div className="electrical-node-head">
        <span className="electrical-node-icon" aria-hidden="true">{nodeIcon(data.kind)}</span>
        <span className="electrical-node-kind">{kindLabel(data.kind)}</span>
        {data.hasChildren && (
          <button
            type="button"
            className="electrical-node-toggle"
            aria-label={`${data.collapsed ? "Développer" : "Replier"} ${data.label}`}
            aria-expanded={!data.collapsed}
            data-testid={`graph-toggle-${data.entityId ?? data.nodeId}`}
            onClick={(event) => {
              event.stopPropagation();
              toggle();
            }}
          >
            {data.collapsed ? "+" : "−"}
          </button>
        )}
        <span className={`dot dot-${data.status === "OK" ? "ok" : data.status === "NON_AFFECTE" ? "warn" : "neutral"}`} title={data.status} />
      </div>
      <strong>{data.label}</strong>
      <small>{data.meta}</small>
      {data.aggregate && (
        <div className="electrical-node-aggregate-counts">
          <span>{data.aggregate.feederCount} départ(s)</span>
          <span>{data.aggregate.loadCount} récepteur(s)</span>
        </div>
      )}
      {data.aggregate && data.onOpenScope && (
        <button
          type="button"
          className="electrical-node-open"
          data-testid={`graph-aggregate-open-${data.aggregate.parentNodeId}`}
          onClick={(event) => {
            event.stopPropagation();
            data.onOpenScope?.();
          }}
        >
          {data.aggregate.targetKind === "board-feeders" ? "Afficher" : "Ouvrir"}
        </button>
      )}
      {isRealNodeKind(data.kind) && data.kind !== "unassigned-group" && (
        <div className="electrical-node-metrics">
          <span>P retenue <b>{formatPower(data.metrics.p_after_ks_w)}</b></span>
          <span>S <b>{formatApparentPower(data.metrics.s_after_ks_va)}</b></span>
          {data.kind === "load" && <span>I <b>{formatCurrent(data.metrics.current_a)}</b></span>}
          {unavailable && <em>résultat non exposé</em>}
        </div>
      )}
      {data.hasChildren && (
        <span className="electrical-node-descendants">
          {data.hiddenCount} {data.hiddenCount === 1 ? "descendant" : "descendants"}
          {data.collapsed ? " masqué(s)" : ""}
        </span>
      )}
      {data.kind === "unassigned-group" && <em>Zone sans rattachement électrique</em>}
    </div>
  );
}

function GraphDiagnostics({ diagnostics }: { diagnostics: ElectricalGraphDiagnostic[] }) {
  const errors = diagnostics.filter((item) => item.severity === "error").length;
  const warnings = diagnostics.filter((item) => item.severity === "warning").length;
  return (
    <div className="graph-diagnostics" data-testid="graph-diagnostics">
      <strong>Diagnostics structurels</strong>
      <span>{errors} erreur(s) · {warnings} avertissement(s)</span>
      {diagnostics.length > 0 && (
        <details>
          <summary>Détail</summary>
          <ul>
            {diagnostics.map((item, index) => (
              <li key={`${item.code}-${item.entityId ?? index}`} title={item.message}>
                <b>{item.code}</b> {item.message}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function selectionNodeId(selection: Selection | null): string | null {
  if (!selection || selection.kind === "project") return null;
  return `${selection.kind}:${selection.id}`;
}

/** Adaptive default keeps small reference projects in their familiar detail view. */
function initialDisplayMode(nodeCount: number): GraphDisplayMode {
  return nodeCount > 120 ? "progressive" : "full";
}

export function ElectricalGraphView({
  project,
  selection,
  onSelect,
}: {
  project: ProjectPayload;
  selection: Selection | null;
  onSelect: (selection: Selection) => void;
}) {
  const graph = useMemo(
    () => buildElectricalGraph(project, { unassignedLoads: project.unassigned_loads ?? [] }),
    [project],
  );
  const descendants = useMemo(() => descendantMap(graph), [graph]);
  const [displayMode, setDisplayMode] = useState<GraphDisplayMode>(() => initialDisplayMode(graph.nodes.length));
  const [showBoardFeeders, setShowBoardFeeders] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());
  const [scope, setScope] = useState<GraphScope>(null);
  const [history, setHistory] = useState<GraphScope[]>([]);
  const [zoom, setZoom] = useState(0.55);
  const [fitRequest, setFitRequest] = useState(0);
  const [flowReady, setFlowReady] = useState(false);
  const [pendingFitId, setPendingFitId] = useState<string | null>(null);
  const flowRef = useRef<ReactFlowInstance<ElectricalFlowNode, Edge> | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const currentNodesRef = useRef<ElectricalFlowNode[]>([]);
  const currentLayoutRef = useRef<ReturnType<typeof layoutElectricalGraph> | null>(null);

  const displayGraph = useMemo(
    () => buildDisplayGraph(graph, {
      scope,
      mode: displayMode,
      source: project.source,
      showBoardFeeders,
    }),
    [graph, scope, displayMode, project.source, showBoardFeeders],
  );
  const displayLayout = useMemo(() => layoutElectricalGraph(displayGraph), [displayGraph]);
  const scopedIds = useMemo(() => scopeNodeIds(graph, scope), [graph, scope]);
  const hiddenByCollapse = useMemo(
    () => (displayMode === "full" ? collapsedDescendantIds(graph, collapsed) : new Set<string>()),
    [graph, displayMode, collapsed],
  );
  const visibleDisplayNodeIds = useMemo(
    () => new Set(displayGraph.nodes.filter((node) => !hiddenByCollapse.has(node.id)).map((node) => node.id)),
    [displayGraph, hiddenByCollapse],
  );
  const selectedNodeId = selectionNodeId(selection);
  const selectedGraphNode = selectedNodeId
    ? graph.nodes.find((node) => node.id === selectedNodeId) ?? null
    : null;
  const selectedHidden = Boolean(selectedGraphNode && !visibleDisplayNodeIds.has(selectedGraphNode.id));
  const selectedOutsideScope = Boolean(selectedGraphNode && !scopedIds.has(selectedGraphNode.id));
  const visibleRealCount = displayGraph.nodes.filter(
    (node) => isRealNodeKind(node.kind) && visibleDisplayNodeIds.has(node.id),
  ).length;
  const totalCount = graph.nodes.length;
  const aggregateCount = displayGraph.aggregateCount;
  const hiddenByAggregation = displayGraph.hiddenRealNodeIds.size;

  const toggleCollapse = useCallback((nodeId: string) => {
    setCollapsed((previous) => {
      const next = new Set(previous);
      if (next.has(nodeId)) next.delete(nodeId);
      else if ((descendants.get(nodeId)?.size ?? 0) > 0) next.add(nodeId);
      return next;
    });
    setFitRequest((value) => value + 1);
  }, [descendants]);

  const expandAll = () => {
    setCollapsed(new Set());
    setFitRequest((value) => value + 1);
  };

  const collapseAll = () => {
    setCollapsed(
      new Set(
        graph.nodes
          .filter((node) => (descendants.get(node.id)?.size ?? 0) > 0)
          .filter((node) => node.kind === "board" || node.kind === "feeder")
          .map((node) => node.id),
      ),
    );
    setFitRequest((value) => value + 1);
  };

  const changeScope = (next: GraphScope) => {
    if (scope !== next) {
      setHistory((previous) => [...previous, scope]);
      setScope(next);
      setShowBoardFeeders(false);
      setFitRequest((value) => value + 1);
    }
  };

  const changeMode = (next: GraphDisplayMode) => {
    if (next !== displayMode) {
      setDisplayMode(next);
      setShowBoardFeeders(false);
      setFitRequest((value) => value + 1);
    }
  };

  const goBack = () => {
    if (history.length === 0) return;
    const previous = history[history.length - 1];
    setHistory(history.slice(0, -1));
    setScope(previous);
    setShowBoardFeeders(false);
    setFitRequest((value) => value + 1);
  };

  const revealSelection = () => {
    if (!selectedGraphNode) return;
    const ancestors = ancestorsForNode(graph, selectedGraphNode.id);
    if (ancestors.length > 0) {
      setCollapsed((previous) => {
        const next = new Set(previous);
        for (const id of ancestors) next.delete(id);
        return next;
      });
    }
    let targetScope: GraphScope = null;
    if (selectedGraphNode.kind === "board" && selectedGraphNode.entityId) {
      targetScope = { kind: "board", id: selectedGraphNode.entityId };
    } else if (selectedGraphNode.kind === "feeder" && selectedGraphNode.entityId) {
      targetScope = { kind: "feeder", id: selectedGraphNode.entityId };
    } else if (selectedGraphNode.kind === "load") {
      const path = pathToNode(graph, selectedGraphNode.id);
      const parentFeeder = [...path].reverse().find((node) => node.kind === "feeder" && node.entityId);
      if (parentFeeder?.entityId) {
        targetScope = { kind: "feeder", id: parentFeeder.entityId };
      } else {
        setDisplayMode("full");
      }
    }
    if (targetScope) setScope(targetScope);
    else if (selectedOutsideScope) setScope(null);
    setPendingFitId(selectedGraphNode.id);
    setFitRequest((value) => value + 1);
  };

  const scopeLabel = scope
    ? graph.nodes.find((node) => node.id === `${scope.kind}:${scope.id}`)?.label ?? scope.id
    : "Installation";
  const scopeNodes = useMemo(() => scopePath(graph, scope), [graph, scope]);
  const canOpenSelectionScope = Boolean(
    selection && (selection.kind === "board" || selection.kind === "feeder"),
  );
  const canToggleBoardFeeders = Boolean(
    displayMode === "progressive" &&
    scope?.kind === "board" &&
    (showBoardFeeders || displayGraph.nodes.some((node) => node.aggregate?.targetKind === "board-feeders")),
  );

  const openAggregate = (aggregate: AggregateNodeInfo) => {
    if (aggregate.targetKind === "board-feeders") {
      setShowBoardFeeders(true);
      setFitRequest((value) => value + 1);
      return;
    }
    changeScope({ kind: aggregate.targetKind, id: aggregate.targetId });
  };

  const nodes = useMemo<ElectricalFlowNode[]>(
    () => displayGraph.nodes.filter((node) => visibleDisplayNodeIds.has(node.id)).map((node) => {
      const hasChildren = isRealNodeKind(node.kind) && (descendants.get(node.id)?.size ?? 0) > 0;
      return {
        id: node.id,
        type: node.kind,
        position: displayLayout.positions[node.id] ?? { x: 0, y: 0 },
        draggable: false,
        selectable: node.selectable,
        selected: isSelected({
          kind: node.kind,
          entityId: node.entityId,
          nodeId: node.id,
          label: node.label,
          meta: node.meta,
          status: node.status,
          metrics: node.metrics,
          groupId: node.groupId,
          collapsed: false,
          hiddenCount: 0,
          hasChildren: false,
          onToggle: () => undefined,
          aggregate: node.aggregate,
        }, selection),
        data: {
          kind: node.kind,
          entityId: node.entityId,
          nodeId: node.id,
          label: node.label,
          meta: node.meta,
          status: node.status,
          metrics: node.metrics,
          groupId: node.groupId,
          collapsed: collapsed.has(node.id),
          hiddenCount: descendants.get(node.id)?.size ?? 0,
          hasChildren,
          onToggle: toggleCollapse,
          aggregate: node.aggregate,
          onOpenScope: node.aggregate ? () => openAggregate(node.aggregate!) : undefined,
        },
      };
    }),
    [displayGraph, displayLayout, visibleDisplayNodeIds, selection, collapsed, descendants, toggleCollapse],
  );
  currentNodesRef.current = nodes;
  currentLayoutRef.current = displayLayout;

  const edges = useMemo<Edge[]>(
    () => displayGraph.edges
      .filter((edge) => visibleDisplayNodeIds.has(edge.source) && visibleDisplayNodeIds.has(edge.target))
      .map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: "smoothstep",
        animated: false,
        selectable: false,
        focusable: false,
        label: edge.aggregated?.label,
        className: edge.aggregated ? "electrical-edge-aggregated" : undefined,
        style: edge.aggregated ? { strokeDasharray: "5 4" } : undefined,
        data: {
          feederId: edge.feederId,
          status: edge.status,
          aggregated: Boolean(edge.aggregated),
        },
      })),
    [displayGraph, visibleDisplayNodeIds],
  );

  const fitByIds = useCallback((
    ids: ReadonlySet<string>,
    padding = 0.18,
    maxZoom = 1.2,
  ) => {
    const instance = flowRef.current;
    const container = containerRef.current;
    const layout = currentLayoutRef.current;
    if (!instance || !container || !layout || ids.size === 0) return;
    const bounds = layoutBounds(layout, ids, GRAPH_NODE_WIDTH, GRAPH_NODE_HEIGHT);
    if (!bounds) return;
    const viewport = computeFitViewport(
      bounds,
      container.clientWidth,
      container.clientHeight,
      padding,
      0.1,
      maxZoom,
    );
    if (!viewport) return;
    // Large complete views use an immediate framing: the target metric is the
    // stable viewport, not an animation that makes 1000 nodes wait.
    const duration = ids.size > 500 ? 0 : 180;
    try {
      instance.setViewport(viewport, { duration });
    } catch {
      // React Flow can be between layout and measurement during tests or first paint.
    }
  }, []);

  const fitVisible = useCallback(() => {
    fitByIds(new Set(currentNodesRef.current.map((node) => node.id)));
  }, [fitByIds]);

  const fitSelection = () => {
    const id = selectionNodeId(selection);
    if (id && visibleDisplayNodeIds.has(id)) {
      fitByIds(new Set([id]), 0.5, 1.35);
    } else if (selectedGraphNode) {
      revealSelection();
    }
  };

  useEffect(() => {
    if (!flowReady || fitRequest === 0) return;
    const timer = window.setTimeout(() => {
      if (pendingFitId) {
        if (visibleDisplayNodeIds.has(pendingFitId)) {
          fitByIds(new Set([pendingFitId]), 0.5, 1.35);
          setPendingFitId(null);
          return;
        }
        setPendingFitId(null);
      }
      fitVisible();
    }, 20);
    return () => window.clearTimeout(timer);
  }, [flowReady, fitRequest, pendingFitId, visibleDisplayNodeIds, fitByIds, fitVisible]);

  const compact = zoom < 0.42;
  const graphTooLarge = displayMode === "full" && scope === null && visibleRealCount > 250;
  const denseBoardView = displayMode === "progressive" && scope?.kind === "board" && showBoardFeeders && visibleRealCount > 250;
  const hiddenSelectionReason = selectedOutsideScope
    ? "hors du périmètre courant"
    : displayMode === "progressive"
      ? "masqué par la vue synthétique"
      : "masqué par le repli";

  return (
    <div className="electrical-graph-shell" data-testid="electrical-graph-view">
      <div className="graph-view-toolbar">
        <nav className="graph-breadcrumb" aria-label="Fil d'Ariane du schéma">
          <button
            type="button"
            className={scope === null ? "is-current" : ""}
            onClick={() => changeScope(null)}
            data-testid="graph-scope-global"
          >
            Installation
          </button>
          {scopeNodes.map((node, index) => {
            const current = index === scopeNodes.length - 1;
            if (node.kind !== "board" && node.kind !== "feeder") return null;
            const scopeKind = node.kind;
            return (
              <span className="graph-breadcrumb-segment" key={node.id}>
                <span aria-hidden="true">›</span>
                <button
                  type="button"
                  className={current ? "is-current" : ""}
                  aria-current={current ? "page" : undefined}
                  onClick={() => changeScope({ kind: scopeKind, id: node.entityId ?? "" })}
                  disabled={current}
                  data-testid={`graph-scope-${node.id}`}
                >
                  {node.label}
                </button>
              </span>
            );
          })}
        </nav>
        <div className="graph-view-actions">
          <button type="button" className="button button-ghost button-small" onClick={goBack} disabled={history.length === 0} data-testid="graph-scope-back">
            Retour
          </button>
          <button type="button" className="button button-ghost button-small" onClick={() => changeScope(null)} data-testid="graph-scope-all">
            Vue globale
          </button>
          {canOpenSelectionScope && (
            <button
              type="button"
              className="button button-secondary button-small"
              onClick={() => {
                if (selection?.kind === "board" || selection?.kind === "feeder") {
                  changeScope({ kind: selection.kind, id: selection.id });
                }
              }}
              data-testid="graph-scope-selection"
            >
              Vue {selection?.kind === "board" ? "tableau" : "départ"}
            </button>
          )}
          <button
            type="button"
            className={`button button-ghost button-small${displayMode === "progressive" ? " is-active" : ""}`}
            onClick={() => changeMode("progressive")}
            data-testid="graph-mode-progressive"
          >
            Vue synthétique
          </button>
          <button
            type="button"
            className={`button button-ghost button-small${displayMode === "full" ? " is-active" : ""}`}
            onClick={() => changeMode("full")}
            data-testid="graph-mode-full"
          >
            Vue complète
          </button>
          {canToggleBoardFeeders && (
            <button
              type="button"
              className="button button-secondary button-small"
              onClick={() => {
                setShowBoardFeeders((value) => !value);
                setFitRequest((value) => value + 1);
              }}
              data-testid="graph-board-feeders"
            >
              {showBoardFeeders ? "Regrouper les départs" : "Afficher les départs"}
            </button>
          )}
          {displayMode === "full" && (
            <>
              <button type="button" className="button button-ghost button-small" onClick={expandAll} data-testid="graph-expand-all">
                Développer tout
              </button>
              <button type="button" className="button button-ghost button-small" onClick={collapseAll} data-testid="graph-collapse-all">
                Réduire tout
              </button>
            </>
          )}
          <button type="button" className="button button-ghost button-small" onClick={fitVisible} data-testid="graph-fit">
            Ajuster
          </button>
          <button type="button" className="button button-ghost button-small" onClick={fitSelection} data-testid="graph-fit-selection">
            Sélection
          </button>
        </div>
      </div>
      <div className="graph-legend">
        <span>Lecture seule</span>
        <span>{visibleRealCount} / {totalCount} équipements</span>
        <span>{edges.length} connexions</span>
        {aggregateCount > 0 && <span>{aggregateCount} branche(s) agrégée(s)</span>}
        {displayMode === "progressive" && <span className="graph-mode-badge">Vue synthétique</span>}
        {hiddenByCollapse.size > 0 && <span>{hiddenByCollapse.size} masqué(s) par repli</span>}
        {hiddenByAggregation > 0 && displayMode === "progressive" && (
          <span>
            {aggregateCount > 0
              ? `${hiddenByAggregation} équipement(s) représenté(s) par agrégat`
              : `${hiddenByAggregation} équipement(s) hors du niveau courant`}
          </span>
        )}
        <span className="graph-zoom-label">Zoom {Math.round(zoom * 100)} %</span>
      </div>
      {scope !== null && (
        <div className="graph-view-context" data-testid="graph-view-context">
          Périmètre : <strong>{scopeLabel}</strong>
        </div>
      )}
      {scope === null && displayMode === "progressive" && (
        <div className="graph-view-context" data-testid="graph-aggregation-context">
          Vue synthétique : les branches terminales sont agrégées ; ouvrez un tableau ou un départ pour le détail.
        </div>
      )}
      {graphTooLarge && (
        <div className="graph-fit-warning" role="status" data-testid="graph-fit-warning">
          Vue complète dense : utilisez la vue synthétique, les vues tableau/départ ou réduisez les branches.
        </div>
      )}
      {denseBoardView && (
        <div className="graph-fit-warning" role="status" data-testid="graph-dense-warning">
          Vue tableau dense : utilisez le zoom, un départ ou « Regrouper les départs » pour une lecture détaillée.
        </div>
      )}
      {selectedHidden && selectedGraphNode && (
        <div className="graph-hidden-selection" role="status" data-testid="graph-hidden-selection">
          <span>L'élément sélectionné « {selectedGraphNode.label} » est {hiddenSelectionReason}.</span>
          <button type="button" className="button button-secondary button-small" onClick={revealSelection} data-testid="graph-reveal-selection">
            Révéler l'équipement
          </button>
        </div>
      )}
      <div
        ref={containerRef}
        className={`electrical-flow${compact ? " is-compact" : ""}`}
        role="application"
        aria-label="Schéma électrique fonctionnel en lecture seule"
      >
        <ReactFlow<ElectricalFlowNode, Edge>
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable
          selectNodesOnDrag={false}
          selectionOnDrag={false}
          fitView={false}
          defaultViewport={{ x: 30, y: 30, zoom: 0.55 }}
          minZoom={0.1}
          maxZoom={2}
          onInit={(instance) => {
            flowRef.current = instance;
            setFlowReady(true);
            setFitRequest((value) => value + 1);
          }}
          onMove={(_, viewport) => {
            setZoom((previous) => Math.abs(previous - viewport.zoom) > 0.02 ? viewport.zoom : previous);
          }}
          onNodeClick={(_, node) => {
            if (node.data.aggregate) {
              openAggregate(node.data.aggregate);
              return;
            }
            const target = nodeSelection(node.data);
            if (target) onSelect(target);
          }}
          onNodeDoubleClick={(_, node) => {
            const target = nodeSelection(node.data);
            if (target && (target.kind === "board" || target.kind === "feeder")) {
              changeScope({ kind: target.kind, id: target.id });
            }
          }}
        >
          <Background variant={BackgroundVariant.Dots} gap={18} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <GraphDiagnostics diagnostics={graph.diagnostics} />
    </div>
  );
}
