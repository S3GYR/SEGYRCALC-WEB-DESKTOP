import { PropertyPanel, type PropertySection } from "../components/PropertyPanel";
import { StatusIndicator } from "../components/StatusIndicator";
import { feederLabel } from "../data/feederReference";
import {
  formatApparentPower,
  formatCurrent,
  formatNumber,
  formatPercent,
  formatPower,
  formatReactivePower,
} from "../format";
import type { ProjectPayload, Selection, TemporaryEdits } from "../types";

function phaseRows(phases: { l1: string | null; l2: string | null; l3: string | null }) {
  return [
    { label: "L1", value: <span className="mono">{formatCurrent(phases.l1)}</span> },
    { label: "L2", value: <span className="mono">{formatCurrent(phases.l2)}</span> },
    { label: "L3", value: <span className="mono">{formatCurrent(phases.l3)}</span> },
  ];
}

export function PropertyContent({
  project,
  selection,
  temporaryEdits,
  onEditDesignation,
  onReset,
}: {
  project: ProjectPayload;
  selection: Selection | null;
  temporaryEdits: TemporaryEdits;
  onEditDesignation: (id: string, value: string) => void;
  onReset: () => void;
}) {
  if (!selection) {
    return <PropertyPanel testId="property-panel" />;
  }

  if (selection.kind === "project") {
    const sections: PropertySection[] = [
      {
        title: "Projet",
        rows: [
          { label: "Nom", value: project.project.name },
          { label: "Référence", value: <span className="mono">{project.project.reference}</span> },
          { label: "Client", value: project.project.client || "—" },
          { label: "Récepteurs", value: project.project.load_count },
          { label: "Tableaux", value: project.project.board_count },
          { label: "Départs", value: project.project.feeder_count },
        ],
      },
      {
        title: "Synthèse moteur",
        rows: [
          { label: "P installée", value: formatPower(project.totals.p_installed_w) },
          { label: "P après Ku", value: formatPower(project.totals.p_after_ku_w) },
          { label: "P retenue", value: formatPower(project.totals.p_after_ks_w) },
          { label: "S retenue", value: formatApparentPower(project.totals.s_after_ks_va) },
          { label: "Courant neutre", value: formatCurrent(project.totals.neutral_current_a) },
          { label: "Déséquilibre", value: formatPercent(project.totals.unbalance_percent) },
        ],
      },
    ];
    return (
      <PropertyPanel
        title={project.project.name}
        subtitle="Projet · lecture seule"
        badge="Projet"
        status={project.status}
        sections={sections}
        diagnostics={project.diagnostics}
        assumptions={project.assumptions}
        testId="property-panel"
      />
    );
  }

  if (selection.kind === "board") {
    const board = project.boards.find((item) => item.id === selection.id);
    if (!board) return <PropertyPanel testId="property-panel" />;
    const sections: PropertySection[] = [
      {
        title: "Identification",
        rows: [
          { label: "Type", value: board.type },
          { label: "Réseau", value: board.network },
          { label: "Tension", value: `${formatNumber(board.voltage_v, 0)} V` },
          { label: "U0", value: board.phase_voltage_v ? `${formatNumber(board.phase_voltage_v, 0)} V` : "—" },
          { label: "Départs", value: board.feeder_count },
          { label: "Récepteurs", value: board.load_count },
        ],
      },
      {
        title: "Résultats du tableau",
        rows: [
          { label: "P installée", value: formatPower(board.p_installed_w) },
          { label: "P après Ku", value: formatPower(board.p_after_ku_w) },
          { label: "P retenue", value: formatPower(board.p_after_ks_w) },
          { label: "S retenue", value: formatApparentPower(board.s_after_ks_va) },
          { label: "Courant neutre", value: formatCurrent(board.neutral_current_a) },
          { label: "Déséquilibre", value: formatPercent(board.unbalance_percent) },
        ],
      },
      { title: "Courants par phase", rows: phaseRows(board.current_phases) },
    ];
    return (
      <PropertyPanel
        title={board.designation}
        subtitle={board.id}
        badge={board.type}
        status={board.status}
        sections={sections}
        diagnostics={board.diagnostics}
        assumptions={project.assumptions}
        testId="property-panel"
      />
    );
  }

  if (selection.kind === "feeder") {
    const feeder = project.feeders.find((item) => item.id === selection.id);
    if (!feeder) return <PropertyPanel testId="property-panel" />;
    const sections: PropertySection[] = [
      {
        title: "Identification",
        rows: [
          { label: "Réseau", value: feeder.network },
          { label: "Tension", value: `${formatNumber(feeder.voltage_v, 0)} V` },
          { label: "Phase", value: feeder.phase ?? "—" },
          { label: "Ks", value: feeder.ks ? formatNumber(feeder.ks) : "—" },
          { label: "Récepteurs", value: feeder.member_count },
          { label: "Tableau", value: <span className="mono">{feeder.parent_board_id}</span> },
        ],
      },
      {
        title: "Résultats du départ",
        rows: [
          { label: "P installée", value: formatPower(feeder.p_installed_w) },
          { label: "P après Ku", value: formatPower(feeder.p_after_ku_w) },
          { label: "P retenue", value: formatPower(feeder.p_after_ks_w) },
          { label: "Q après Ks", value: formatReactivePower(feeder.q_after_ks_var) },
          { label: "S retenue", value: formatApparentPower(feeder.s_after_ks_va) },
          { label: "Courant neutre", value: formatCurrent(feeder.neutral_current_a) },
          { label: "Déséquilibre", value: formatPercent(feeder.unbalance_percent) },
        ],
      },
      { title: "Courants par phase", rows: phaseRows(feeder.current_phases) },
    ];
    return (
      <PropertyPanel
        title={feederLabel(feeder)}
        subtitle={feeder.id}
        badge="Départ"
        status={feeder.status}
        sections={sections}
        diagnostics={feeder.diagnostics}
        assumptions={project.assumptions}
        testId="property-panel"
      />
    );
  }

  const load = project.loads.find((item) => item.id === selection.id);
  if (!load) return <PropertyPanel testId="property-panel" />;
  const feeder = project.feeders.find((item) => item.id === load.feeder_id);
  const editedName = temporaryEdits[load.id]?.designation;
  const isModified = Boolean(editedName);
  const sections: PropertySection[] = [
    {
      title: "Récepteur",
      rows: [
        { label: "Réseau", value: load.network },
        { label: "Tension", value: `${formatNumber(load.voltage_v, 0)} V` },
        { label: "Quantité", value: load.quantity },
        { label: "Puissance nominale", value: `${formatNumber(load.nominal_power)} ${load.power_unit}` },
        { label: "Cos φ", value: load.power_factor ? formatNumber(load.power_factor) : "—" },
        { label: "Ku", value: formatNumber(load.ku) },
        { label: "Ks du départ", value: load.ks ? formatNumber(load.ks) : "—" },
        { label: "Phase", value: load.phase ?? "—" },
      ],
    },
    {
      title: "Rattachement",
      rows: [
        { label: "Tableau", value: <span className="mono">{load.parent_board_id}</span> },
        { label: "Départ", value: feeder?.designation ?? <span className="mono">{load.feeder_id}</span> },
        { label: "Départ ID", value: <span className="mono">{load.feeder_id}</span> },
      ],
    },
    {
      title: "Résultats disponibles",
      rows: [
        { label: "P installée", value: formatPower(load.installed_power_w) },
        { label: "P après Ku", value: formatPower(load.p_after_ku_w) },
        { label: "P retenue", value: formatPower(load.p_after_ks_w) },
        { label: "Q après Ku", value: formatReactivePower(load.q_after_ku_var) },
        { label: "Q après Ks", value: formatReactivePower(load.q_after_ks_var) },
        { label: "S récepteur", value: load.apparent_power_available ? formatApparentPower(load.s_after_ks_va) : <span className="unavailable-value">Non exposé par le moteur</span> },
        { label: "I récepteur", value: load.current_available ? formatCurrent(load.current_a) : <span className="unavailable-value">Non exposé par le moteur</span> },
      ],
    },
  ];
  return (
    <PropertyPanel
      title={editedName ?? load.designation}
      subtitle={load.id}
      badge="Récepteur"
      status={load.status}
      sections={sections}
      diagnostics={load.diagnostics}
      assumptions={project.assumptions}
      designation={editedName ?? load.designation}
      modified={isModified}
      onEditDesignation={(value) => onEditDesignation(load.id, value)}
      onReset={onReset}
      testId="property-panel"
    />
  );
}

export function SelectionStatus({ selection, project }: { selection: Selection | null; project: ProjectPayload }) {
  if (!selection) return null;
  if (selection.kind === "project") return <StatusIndicator status={project.status} compact />;
  const entity = selection.kind === "board"
    ? project.boards.find((item) => item.id === selection.id)
    : selection.kind === "feeder"
      ? project.feeders.find((item) => item.id === selection.id)
      : project.loads.find((item) => item.id === selection.id);
  return entity ? <StatusIndicator status={entity.status} compact /> : null;
}
