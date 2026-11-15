import { feederLabel } from "./feederReference";
import type { BoardSummary, FeederSummary, LoadSummary, ProjectPayload, Selection, TreeNode } from "../types";

function loadNode(load: LoadSummary): TreeNode {
  return {
    id: load.id,
    kind: "load",
    label: load.designation,
    meta: `${load.id} — ${load.network} — ${load.quantity} u.`,
    status: load.status,
    selection: { kind: "load", id: load.id },
    selectable: true,
  };
}

function emptyFeederNode(feeder: FeederSummary): TreeNode {
  return {
    // Presentation-only key. This is deliberately not a receivable id.
    id: `empty:${feeder.id}`,
    kind: "empty",
    label: "Aucun récepteur",
    meta: "Départ sans récepteur",
    status: "NON_CALCULABLE",
    selectable: false,
  };
}

function unassignedGroup(project: ProjectPayload, loads: LoadSummary[]): TreeNode | null {
  const advertised = project.project.unassigned_load_count ?? 0;
  const listed = project.coherence.unassigned_load_ids?.length ?? 0;
  const assigned = new Set(project.loads.map((load) => load.id));
  const seen = new Set<string>();
  const uniqueLoads = loads.filter((load) => {
    if (assigned.has(load.id) || seen.has(load.id)) return false;
    seen.add(load.id);
    return true;
  });
  const count = Math.max(advertised, listed, uniqueLoads.length);
  if (count === 0) return null;
  return {
    id: "unassigned-group",
    kind: "unassigned-group",
    label: `Récepteurs non affectés (${count})`,
    meta: uniqueLoads.length > 0
      ? "Sans départ — rattachement existant requis"
      : "Détail non exposé par le contrat actuel",
    status: uniqueLoads.length > 0 ? "WARN" : "NON_CALCULABLE",
    children: uniqueLoads.map(loadNode),
    selectable: false,
  };
}

export function buildElectricalTree(
  project: ProjectPayload,
  unassignedLoads: LoadSummary[] = project.unassigned_loads ?? [],
): TreeNode[] {
  const boards = new Map(project.boards.map((board) => [board.id, board]));
  const loadsByFeeder = new Map<string, LoadSummary[]>();
  for (const load of project.loads) {
    const list = loadsByFeeder.get(load.feeder_id) ?? [];
    list.push(load);
    loadsByFeeder.set(load.feeder_id, list);
  }
  const root = project.boards.find((board) => board.type === "TGBT")
    ?? project.boards.find((board) => !project.feeders.some((feeder) => feeder.downstream_board_id === board.id))
    ?? project.boards[0];
  const visited = new Set<string>();

  const boardNode = (board: BoardSummary): TreeNode => {
    if (visited.has(board.id)) {
      return {
        id: board.id,
        kind: "board",
        label: board.designation,
        meta: `${board.type} — cycle`,
        status: board.status,
        selection: { kind: "board", id: board.id },
        selectable: true,
      };
    }
    visited.add(board.id);
    const children = project.feeders
      .filter((feeder) => feeder.parent_board_id === board.id)
      .map((feeder) => feederNode(feeder));
    return {
      id: board.id,
      kind: "board",
      label: board.designation,
      meta: `${board.type} — ${board.network} — ${board.feeder_count} départ(s)`,
      status: board.status,
      children,
      selection: { kind: "board", id: board.id },
      selectable: true,
    };
  };

  const feederNode = (feeder: FeederSummary): TreeNode => {
    const downstream = feeder.downstream_board_id ? boards.get(feeder.downstream_board_id) : undefined;
    const children: TreeNode[] = downstream
      ? [boardNode(downstream)]
      : (loadsByFeeder.get(feeder.id) ?? []).map((load) => loadNode(load));
    if (!downstream && children.length === 0) {
      children.push(emptyFeederNode(feeder));
    }
    return {
      id: feeder.id,
      kind: "feeder",
      label: feederLabel(feeder),
      meta: `${feeder.id} — ${feeder.member_count} récepteur(s)`,
      status: feeder.status,
      children,
      selection: { kind: "feeder", id: feeder.id },
      selectable: true,
    };
  };

  const rootNodes: TreeNode[] = root ? [boardNode(root)] : [];
  const section = unassignedGroup(project, unassignedLoads);
  if (section) rootNodes.push(section);
  if (rootNodes.length === 0) return [];
  return [{
    id: "project",
    kind: "project",
    label: project.project.name,
    meta: `${project.project.reference} — lecture seule`,
    status: project.status,
    children: rootNodes,
    selection: { kind: "project", id: "project" },
    selectable: true,
  }];
}

export function selectionLabel(selection: Selection | null, project: ProjectPayload | null): string {
  if (!selection || !project) return "Aucune sélection";
  if (selection.kind === "project") return project.project.name;
  if (selection.kind === "board") return project.boards.find((board) => board.id === selection.id)?.designation ?? selection.id;
  if (selection.kind === "feeder") {
    const feeder = project.feeders.find((item) => item.id === selection.id);
    return feeder ? feederLabel(feeder) : selection.id;
  }
  const load = project.loads.find((item) => item.id === selection.id)
    ?? project.unassigned_loads?.find((item) => item.id === selection.id);
  return load?.designation ?? selection.id;
}

export function feederById(project: ProjectPayload | null, id: string | null): FeederSummary | null {
  if (!project || !id) return null;
  return project.feeders.find((feeder) => feeder.id === id) ?? null;
}

export function loadById(project: ProjectPayload | null, id: string | null): LoadSummary | null {
  if (!project || !id) return null;
  return project.loads.find((load) => load.id === id)
    ?? project.unassigned_loads?.find((load) => load.id === id)
    ?? null;
}

export function boardById(project: ProjectPayload | null, id: string | null): BoardSummary | null {
  if (!project || !id) return null;
  return project.boards.find((board) => board.id === id) ?? null;
}

export function feederName(project: ProjectPayload, feederId: string): string {
  const feeder = project.feeders.find((item) => item.id === feederId);
  return feeder ? feederLabel(feeder) : feederId;
}

export function loadName(project: ProjectPayload, loadId: string): string {
  return loadById(project, loadId)?.designation ?? loadId;
}
