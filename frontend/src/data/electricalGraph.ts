import { feederLabel } from "./feederReference";
import type { BoardSummary, FeederSummary, LoadSummary, ProjectPayload } from "../types";

/**
 * Read-only, dependency-free projection of an existing ProjectPayload.
 *
 * This module deliberately does not evaluate P/Q/S/I or any electrical rule.
 * It only copies the values already produced by the backend engine into graph
 * references so a future renderer can display them without recalculating.
 */

export type ElectricalGraphNodeKind = "board" | "feeder" | "load" | "unassigned-group";
export type ElectricalGraphEdgeKind = "board-to-feeder" | "feeder-to-board" | "feeder-to-load";
export type ElectricalGraphDiagnosticSeverity = "info" | "warning" | "error";

export type ElectricalGraphDiagnostic = {
  code: string;
  severity: ElectricalGraphDiagnosticSeverity;
  message: string;
  entityId?: string;
  field?: string;
};

export type ElectricalGraphMetrics = {
  p_installed_w: string | null;
  p_after_ku_w: string | null;
  p_after_ks_w: string | null;
  q_after_ks_var: string | null;
  s_after_ks_va: string | null;
  current_a: string | null;
  neutral_current_a: string | null;
  unbalance_percent: string | null;
};

export type ElectricalGraphNode = {
  /** Stable graph key, prefixed by entity type to avoid cross-type collisions. */
  id: string;
  kind: ElectricalGraphNodeKind;
  /** Original business id; null only for the presentation-only unassigned group. */
  entityId: string | null;
  label: string;
  meta: string;
  status: string;
  selectable: boolean;
  /** Set only on unassigned receiver nodes. */
  groupId?: string;
  /** Existing engine values, copied as read-only references. */
  metrics: ElectricalGraphMetrics;
};

export type ElectricalGraphEdge = {
  id: string;
  kind: ElectricalGraphEdgeKind;
  source: string;
  target: string;
  feederId: string;
  label: string;
  status: string;
};

export type ElectricalGraph = {
  nodes: ElectricalGraphNode[];
  edges: ElectricalGraphEdge[];
  diagnostics: ElectricalGraphDiagnostic[];
};

export type ElectricalGraphOptions = {
  /**
   * Full unassigned receiver records, if the caller has them. The current
   * backend payload does not expose them; passing ids only is not sufficient
   * to create a selectable receiver node.
   */
  unassignedLoads?: LoadSummary[];
};

const emptyMetrics: ElectricalGraphMetrics = {
  p_installed_w: null,
  p_after_ku_w: null,
  p_after_ks_w: null,
  q_after_ks_var: null,
  s_after_ks_va: null,
  current_a: null,
  neutral_current_a: null,
  unbalance_percent: null,
};

function boardMetrics(board: BoardSummary): ElectricalGraphMetrics {
  return {
    p_installed_w: board.p_installed_w,
    p_after_ku_w: board.p_after_ku_w,
    p_after_ks_w: board.p_after_ks_w,
    q_after_ks_var: board.q_after_ks_var,
    s_after_ks_va: board.s_after_ks_va,
    current_a: null,
    neutral_current_a: board.neutral_current_a,
    unbalance_percent: board.unbalance_percent,
  };
}

function feederMetrics(feeder: FeederSummary): ElectricalGraphMetrics {
  return {
    p_installed_w: feeder.p_installed_w,
    p_after_ku_w: feeder.p_after_ku_w,
    p_after_ks_w: feeder.p_after_ks_w,
    q_after_ks_var: feeder.q_after_ks_var,
    s_after_ks_va: feeder.s_after_ks_va,
    current_a: null,
    neutral_current_a: feeder.neutral_current_a,
    unbalance_percent: feeder.unbalance_percent,
  };
}

function loadMetrics(load: LoadSummary): ElectricalGraphMetrics {
  return {
    p_installed_w: load.installed_power_w,
    p_after_ku_w: load.p_after_ku_w,
    p_after_ks_w: load.p_after_ks_w,
    q_after_ks_var: load.q_after_ks_var,
    s_after_ks_va: load.s_after_ks_va,
    current_a: load.current_a,
    neutral_current_a: null,
    unbalance_percent: null,
  };
}

function boardNode(board: BoardSummary): ElectricalGraphNode {
  return {
    id: `board:${board.id}`,
    kind: "board",
    entityId: board.id,
    label: board.designation,
    meta: `${board.type} — ${board.network} — ${board.voltage_v} V — ${board.feeder_count} départ(s)`,
    status: board.status,
    selectable: true,
    metrics: boardMetrics(board),
  };
}

function feederNode(feeder: FeederSummary): ElectricalGraphNode {
  return {
    id: `feeder:${feeder.id}`,
    kind: "feeder",
    entityId: feeder.id,
    label: feederLabel(feeder),
    meta: `${feeder.id} — ${feeder.network} ${feeder.voltage_v} V — ${feeder.downstream_board_id ? "vers tableau" : `${feeder.member_count} récepteur(s)`}`,
    status: feeder.status,
    selectable: true,
    metrics: feederMetrics(feeder),
  };
}

function loadNode(load: LoadSummary, groupId?: string): ElectricalGraphNode {
  return {
    id: `load:${load.id}`,
    kind: "load",
    entityId: load.id,
    label: load.designation,
    meta: `${load.id} — ${load.network} — ${load.quantity} u.`,
    status: load.status,
    selectable: true,
    groupId,
    metrics: loadMetrics(load),
  };
}

function diagnostic(
  code: string,
  severity: ElectricalGraphDiagnosticSeverity,
  message: string,
  entityId?: string,
  field?: string,
): ElectricalGraphDiagnostic {
  return { code, severity, message, entityId, field };
}

/**
 * Build the graph projection. The input object is never mutated and the
 * output is fully deterministic for a given payload and options.
 */
export function buildElectricalGraph(
  project: ProjectPayload,
  options: ElectricalGraphOptions = {},
): ElectricalGraph {
  const diagnostics: ElectricalGraphDiagnostic[] = [];
  const boards = project.boards.slice();
  const feeders = project.feeders.slice();
  const loads = project.loads.slice();
  const boardById = new Map(boards.map((board) => [board.id, board]));
  const feederById = new Map(feeders.map((feeder) => [feeder.id, feeder]));
  const loadsByFeeder = new Map<string, LoadSummary[]>();
  for (const load of loads) {
    const list = loadsByFeeder.get(load.feeder_id) ?? [];
    list.push(load);
    loadsByFeeder.set(load.feeder_id, list);
  }

  const roots = boards.filter((board) => !board.parent_feeder_id);
  const root = roots.find((board) => board.type === "TGBT") ?? roots[0] ?? boards[0];
  if (boards.length === 0) {
    diagnostics.push(diagnostic("NO_BOARD", "error", "Le projet ne contient aucun tableau.", undefined, "boards"));
  } else if (roots.length === 0) {
    diagnostics.push(diagnostic("NO_ROOT", "error", "Aucun tableau racine sans départ parent.", root?.id, "boards"));
  } else if (roots.length > 1) {
    diagnostics.push(diagnostic("MULTIPLE_ROOTS", "warning", "Plusieurs tableaux racine sont présents.", undefined, "boards"));
  }
  const tgbts = boards.filter((board) => board.type === "TGBT");
  if (tgbts.length > 1) {
    diagnostics.push(diagnostic("MULTIPLE_TGBT", "warning", "Plusieurs tableaux de type TGBT sont présents.", undefined, "boards"));
  }

  const nodes: ElectricalGraphNode[] = boards.map(boardNode);
  nodes.push(...feeders.map(feederNode));
  nodes.push(...loads.map((load) => loadNode(load)));

  for (const board of boards) {
    if (!feeders.some((feeder) => feeder.parent_board_id === board.id)) {
      diagnostics.push(diagnostic(
        "EMPTY_BOARD",
        "info",
        `Le tableau ${board.id} ne possède aucun départ.`,
        board.id,
        "feeders",
      ));
    }
  }

  const edges: ElectricalGraphEdge[] = [];
  const edgeIds = new Set<string>();
  const pushEdge = (edge: ElectricalGraphEdge) => {
    if (edgeIds.has(edge.id)) {
      diagnostics.push(diagnostic("DUPLICATE_EDGE", "error", `Arête dupliquée: ${edge.id}`, edge.feederId, "edges"));
      return;
    }
    edgeIds.add(edge.id);
    edges.push(edge);
  };

  for (const feeder of feeders) {
    const parent = boardById.get(feeder.parent_board_id);
    if (!parent) {
      diagnostics.push(diagnostic(
        "FEEDER_PARENT_MISSING",
        "error",
        `Le tableau parent ${feeder.parent_board_id} du départ ${feeder.id} est absent.`,
        feeder.id,
        "parent_board_id",
      ));
    } else {
      pushEdge({
        id: `edge:board:${parent.id}->feeder:${feeder.id}`,
        kind: "board-to-feeder",
        source: `board:${parent.id}`,
        target: `feeder:${feeder.id}`,
        feederId: feeder.id,
        label: feederLabel(feeder),
        status: feeder.status,
      });
    }

    const memberLoads = loadsByFeeder.get(feeder.id) ?? [];
    if (feeder.downstream_board_id) {
      const child = boardById.get(feeder.downstream_board_id);
      if (!child) {
        diagnostics.push(diagnostic(
          "DOWNSTREAM_BOARD_MISSING",
          "error",
          `Le tableau aval ${feeder.downstream_board_id} du départ ${feeder.id} est absent.`,
          feeder.id,
          "downstream_board_id",
        ));
      } else {
        pushEdge({
          id: `edge:feeder:${feeder.id}->board:${child.id}`,
          kind: "feeder-to-board",
          source: `feeder:${feeder.id}`,
          target: `board:${child.id}`,
          feederId: feeder.id,
          label: feederLabel(feeder),
          status: feeder.status,
        });
        if (child.parent_feeder_id !== feeder.id) {
          diagnostics.push(diagnostic(
            "INCONSISTENT_PARENT",
            "error",
            `Le tableau ${child.id} ne référence pas le départ ${feeder.id}.`,
            child.id,
            "parent_feeder_id",
          ));
        }
      }
    }
    if (memberLoads.length > 0) {
      for (const load of memberLoads) {
        pushEdge({
          id: `edge:feeder:${feeder.id}->load:${load.id}`,
          kind: "feeder-to-load",
          source: `feeder:${feeder.id}`,
          target: `load:${load.id}`,
          feederId: feeder.id,
          label: feederLabel(feeder),
          status: load.status,
        });
      }
    }
    if (feeder.downstream_board_id && memberLoads.length > 0) {
      diagnostics.push(diagnostic(
        "MIXED_FEEDER_DESTINATION",
        "error",
        `Le départ ${feeder.id} déclare à la fois un tableau aval et des récepteurs.`,
        feeder.id,
        "feeder",
      ));
    }
    if (!feeder.downstream_board_id && memberLoads.length === 0) {
      diagnostics.push(diagnostic(
        "EMPTY_FEEDER",
        "info",
        `Le départ ${feeder.id} n'a ni récepteur ni tableau aval.`,
        feeder.id,
        "feeder",
      ));
    }
    if (feeder.member_count !== memberLoads.length) {
      diagnostics.push(diagnostic(
        "MEMBER_COUNT_MISMATCH",
        "warning",
        `Le départ ${feeder.id} annonce ${feeder.member_count} récepteur(s) mais en expose ${memberLoads.length}.`,
        feeder.id,
        "member_count",
      ));
    }
  }

  for (const load of loads) {
    if (!feederById.has(load.feeder_id)) {
      diagnostics.push(diagnostic(
        "LOAD_FEEDER_MISSING",
        "error",
        `Le départ ${load.feeder_id} du récepteur ${load.id} est absent.`,
        load.id,
        "feeder_id",
      ));
    }
  }

  // Reachability and cycle diagnostics are computed without changing nodes or
  // edges. The projection never repairs an invalid project silently.
  if (root) {
    const downstream = new Map<string, string[]>();
    for (const feeder of feeders) {
      if (!feeder.downstream_board_id || !boardById.has(feeder.downstream_board_id)) continue;
      const list = downstream.get(feeder.parent_board_id) ?? [];
      list.push(feeder.downstream_board_id);
      downstream.set(feeder.parent_board_id, list);
    }
    const visited = new Set<string>();
    const visiting = new Set<string>();
    const walk = (boardId: string) => {
      if (visiting.has(boardId)) {
        diagnostics.push(diagnostic(
          "CYCLE_DETECTED",
          "error",
          `Cycle de tableaux détecté à partir de ${boardId}.`,
          boardId,
          "boards",
        ));
        return;
      }
      if (visited.has(boardId)) return;
      visiting.add(boardId);
      for (const child of downstream.get(boardId) ?? []) walk(child);
      visiting.delete(boardId);
      visited.add(boardId);
    };
    walk(root.id);
    for (const board of boards) {
      if (!visited.has(board.id)) {
        diagnostics.push(diagnostic(
          "ORPHAN_BOARD",
          "warning",
          `Le tableau ${board.id} n'est pas atteignable depuis le tableau racine.`,
          board.id,
          "boards",
        ));
      }
    }
    for (const feeder of feeders) {
      if (!visited.has(feeder.parent_board_id)) {
        diagnostics.push(diagnostic(
          "ORPHAN_FEEDER",
          "warning",
          `Le départ ${feeder.id} n'est pas atteignable depuis le tableau racine.`,
          feeder.id,
          "feeders",
        ));
      }
    }
  }

  const assignedIds = new Set(loads.map((load) => load.id));
  const seenUnassigned = new Set<string>();
  const availableUnassigned = (options.unassignedLoads ?? project.unassigned_loads ?? [])
    .filter((load) => {
      if (assignedIds.has(load.id) || seenUnassigned.has(load.id)) return false;
      seenUnassigned.add(load.id);
      return true;
    });
  const unassignedIds = project.coherence.unassigned_load_ids ?? [];
  const unassignedCount = Math.max(
    project.project.unassigned_load_count ?? 0,
    unassignedIds.length,
    availableUnassigned.length,
  );
  if (unassignedCount > 0) {
    const groupId = "unassigned";
    nodes.push({
      id: "group:unassigned",
      kind: "unassigned-group",
      entityId: null,
      label: `Récepteurs non affectés (${unassignedCount})`,
      meta: availableUnassigned.length > 0
        ? "Zone distincte, sans rattachement électrique"
        : "Détail non exposé par le contrat actuel",
      status: availableUnassigned.length > 0 ? "WARN" : "NON_CALCULABLE",
      selectable: false,
      metrics: emptyMetrics,
    });
    for (const load of availableUnassigned) {
      nodes.push(loadNode(load, groupId));
    }
    if (availableUnassigned.length < unassignedCount) {
      diagnostics.push(diagnostic(
        "UNASSIGNED_LOAD_DETAILS_UNAVAILABLE",
        "warning",
        `${unassignedCount} récepteur(s) non affecté(s) annoncé(s), ${availableUnassigned.length} détail(s) disponible(s).`,
        undefined,
        "unassigned_loads",
      ));
    }
  }

  return { nodes, edges, diagnostics };
}
