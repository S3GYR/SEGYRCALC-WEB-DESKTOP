import { feederLabel } from "./feederReference";
import type { BoardSummary, FeederSummary, LoadSummary, ProjectPayload, Selection, TreeNode } from "../types";

export function buildElectricalTree(project: ProjectPayload): TreeNode[] {
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
        id: board.id, kind: "board", label: board.designation, meta: `${board.type} · cycle`, status: board.status,
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
      meta: `${board.type} · ${board.network} · ${board.feeder_count} départ(s)`,
      status: board.status,
      children,
    };
  };

  const feederNode = (feeder: FeederSummary): TreeNode => {
    const downstream = feeder.downstream_board_id ? boards.get(feeder.downstream_board_id) : undefined;
    const children: TreeNode[] = downstream
      ? [boardNode(downstream)]
      : (loadsByFeeder.get(feeder.id) ?? []).map((load) => ({
          id: load.id,
          kind: "load",
          label: load.designation,
          meta: `${load.id} · ${load.network} · ${load.quantity} u.`,
          status: load.status,
        }));
    if (feeder.designation && !downstream && children.length === 0) {
      children.push({
        id: `${feeder.id}-empty`,
        kind: "load",
        label: "Aucun récepteur",
        meta: feeder.id,
        status: "NON_CALCULABLE",
      });
    }
    return {
      id: feeder.id,
      kind: "feeder",
      label: feederLabel(feeder),
      meta: `${feeder.id} · ${feeder.member_count} récepteur(s)`,
      status: feeder.status,
      children,
    };
  };

  if (!root) return [];
  return [{
    id: "project",
    kind: "project",
    label: project.project.name,
    meta: `${project.project.reference} · lecture seule`,
    status: project.status,
    children: [boardNode(root)],
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
  return project.loads.find((load) => load.id === selection.id)?.designation ?? selection.id;
}

export function feederById(project: ProjectPayload | null, id: string | null): FeederSummary | null {
  if (!project || !id) return null;
  return project.feeders.find((feeder) => feeder.id === id) ?? null;
}

export function loadById(project: ProjectPayload | null, id: string | null): LoadSummary | null {
  if (!project || !id) return null;
  return project.loads.find((load) => load.id === id) ?? null;
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
  return project.loads.find((load) => load.id === loadId)?.designation ?? loadId;
}
