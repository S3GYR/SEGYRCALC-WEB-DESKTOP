import { useMemo, useState } from "react";
import { CoefficientEditor } from "../components/CoefficientEditor";
import { ComparisonPanel } from "../components/ComparisonPanel";
import { DataTable, type DataColumn, type SortState } from "../components/DataTable";
import { PageHeader } from "../components/PageHeader";
import { PhaseBalancePanel } from "../components/PhaseBalancePanel";
import { SearchInput } from "../components/SearchInput";
import { StatusIndicator } from "../components/StatusIndicator";
import { SummaryCard } from "../components/SummaryCard";
import { Tabs } from "../components/Tabs";
import { Toolbar } from "../components/Toolbar";
import { TraceabilityPanel } from "../components/TraceabilityPanel";
import { TreeView } from "../components/TreeView";
import { UnitDisplay } from "../components/UnitDisplay";
import { feederLabel } from "../data/feederReference";
import { buildElectricalTree } from "../data/hierarchy";
import {
  compareNumeric,
  compareText,
  formatApparentPower,
  formatCurrent,
  formatNumber,
  formatPercent,
  formatPower,
  formatReactivePower,
} from "../format";
import { Icon } from "../icons";
import type { BoardSummary, FeederSummary, LoadSummary, ProjectPayload, Selection, TemporaryEdits } from "../types";
import { PropertyContent } from "./PropertyContent";

type View = "feeders" | "loads" | "boards" | "tgbt";

function feederSearchText(feeder: FeederSummary): string {
  return `${feeder.id} ${feederLabel(feeder)} ${feeder.parent_board_id} ${feeder.network} ${feeder.status}`.toLocaleLowerCase("fr");
}

function loadSearchText(load: LoadSummary): string {
  return `${load.id} ${load.designation} ${load.feeder_id} ${load.parent_board_id} ${load.network} ${load.status}`.toLocaleLowerCase("fr");
}

function boardSearchText(board: BoardSummary): string {
  return `${board.id} ${board.designation} ${board.type} ${board.network} ${board.status}`.toLocaleLowerCase("fr");
}

function filterRows<T>(rows: T[], search: string, board: string, status: string, get: (row: T) => { boardId: string; status: string; text: string }): T[] {
  const needle = search.trim().toLocaleLowerCase("fr");
  return rows.filter((row) => {
    const meta = get(row);
    if (board !== "all" && meta.boardId !== board) return false;
    if (status !== "all" && meta.status !== status) return false;
    return !needle || meta.text.includes(needle);
  });
}

function sortRows<T>(rows: T[], sort: SortState | null, value: (row: T, key: string) => string | null | undefined, text: (row: T, key: string) => string): T[] {
  if (!sort) return rows;
  const copy = [...rows];
  copy.sort((left, right) => {
    const a = value(left, sort.key);
    const b = value(right, sort.key);
    const isNumeric = ["p_installed_w", "p_after_ku_w", "p_after_ks_w", "q_after_ku_var", "q_after_ks_var", "s_after_ku_va", "s_after_ks_va", "installed_power_w", "power_factor", "ku", "ks", "quantity", "neutral_current_a", "unbalance_percent"].includes(sort.key);
    const comparison = isNumeric ? compareNumeric(a, b) : compareText(text(left, sort.key), text(right, sort.key));
    return sort.direction === "asc" ? comparison : -comparison;
  });
  return copy;
}

function filterOptions(project: ProjectPayload) {
  const statuses = new Set<string>();
  project.boards.forEach((item) => statuses.add(item.status));
  project.feeders.forEach((feeder) => statuses.add(feeder.status));
  project.loads.forEach((load) => statuses.add(load.status));
  return [...statuses].sort();
}

export function PowerBalanceScreen({
  project,
  previousProject,
  selection,
  onSelect,
  temporaryEdits,
  onEditDesignation,
  onEditCoefficient,
  onReset,
}: {
  project: ProjectPayload;
  previousProject: ProjectPayload | null;
  selection: Selection | null;
  onSelect: (selection: Selection) => void;
  temporaryEdits: TemporaryEdits;
  onEditDesignation: (id: string, value: string) => void;
  onEditCoefficient: (kind: "load" | "feeder", id: string, value: string) => void;
  onReset: () => void;
}) {
  const [view, setView] = useState<View>("loads");
  const [search, setSearch] = useState("");
  const [boardFilter, setBoardFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sort, setSort] = useState<SortState | null>({ key: "designation", direction: "asc" });
  const [treeWidth, setTreeWidth] = useState(235);
  const [propertyWidth, setPropertyWidth] = useState(290);
  const tree = useMemo(
    () => buildElectricalTree(project, project.unassigned_loads ?? []),
    [project],
  );
  const board = project.boards.find((item) => item.id === boardFilter) ?? null;
  const statuses = useMemo(() => filterOptions(project), [project]);

  const displayLoad = (load: LoadSummary): LoadSummary => {
    const editedName = temporaryEdits[load.id]?.designation;
    return editedName ? { ...load, designation: editedName } : load;
  };

  const filteredFeeders = useMemo(() => {
    const rows = filterRows(project.feeders, search, boardFilter, statusFilter, (feeder) => ({
      boardId: feeder.parent_board_id,
      status: feeder.status,
      text: feederSearchText(feeder),
    }));
    return sortRows(rows, sort, (row, key) => {
      if (key === "designation") return row.designation;
      if (key === "network") return row.network;
      if (key === "p_installed_w") return row.p_installed_w;
      if (key === "p_after_ku_w") return row.p_after_ku_w;
      if (key === "p_after_ks_w") return row.p_after_ks_w;
      if (key === "s_after_ks_va") return row.s_after_ks_va;
      return row.designation;
    }, (row, key) => String((row as unknown as Record<string, unknown>)[key] ?? ""));
  }, [project.feeders, search, boardFilter, statusFilter, sort]);

  const filteredLoads = useMemo(() => {
    const rows = filterRows(project.loads, search, boardFilter, statusFilter, (load) => ({
      boardId: load.parent_board_id,
      status: load.status,
      text: `${loadSearchText(load)} ${temporaryEdits[load.id]?.designation ?? ""}`,
    }));
    return sortRows(rows, sort, (row, key) => {
      if (key === "designation") return row.designation;
      if (key === "network") return row.network;
      if (key === "installed_power_w") return row.installed_power_w;
      if (key === "power_factor") return row.power_factor;
      if (key === "ku") return row.ku;
      if (key === "p_after_ks_w") return row.p_after_ks_w;
      if (key === "quantity") return String(row.quantity);
      return row.designation;
    }, (row, key) => String((row as unknown as Record<string, unknown>)[key] ?? ""));
  }, [project.loads, search, boardFilter, statusFilter, sort, temporaryEdits]);

  const filteredBoards = useMemo(() => {
    const rows = filterRows(project.boards, search, "all", statusFilter, (item) => ({
      boardId: item.id,
      status: item.status,
      text: boardSearchText(item),
    }));
    return sortRows(rows, sort, (row, key) => {
      if (key === "designation") return row.designation;
      if (key === "network") return row.network;
      if (key === "p_installed_w") return row.p_installed_w;
      if (key === "p_after_ku_w") return row.p_after_ku_w;
      if (key === "p_after_ks_w") return row.p_after_ks_w;
      if (key === "q_after_ks_var") return row.q_after_ks_var;
      if (key === "s_after_ks_va") return row.s_after_ks_va;
      return row.designation;
    }, (row, key) => String((row as unknown as Record<string, unknown>)[key] ?? ""));
  }, [project.boards, search, statusFilter, sort]);

  const feederColumns: Array<DataColumn<FeederSummary>> = [
    { key: "id", label: "Référence", width: 92, render: (row) => <span className="mono">{row.id}</span> },
    { key: "designation", label: "Désignation", width: 190, sortable: true, render: (row) => <span className="cell-main">{row.designation}</span> },
    { key: "type", label: "Type", width: 78, render: (row) => <span className="badge badge-outline">{row.downstream_board_id ? "Tableau" : "Départ"}</span> },
    { key: "member_count", label: "Qté", width: 52, align: "right", render: (row) => row.member_count },
    { key: "voltage_v", label: "Tension", width: 80, align: "right", render: (row) => `${formatNumber(row.voltage_v, 0)} V` },
    { key: "network", label: "Réseau", width: 68, sortable: true, render: (row) => row.network },
    { key: "p_installed_w", label: "P inst.", width: 90, align: "right", sortable: true, render: (row) => formatPower(row.p_installed_w) },
    { key: "p_after_ku_w", label: "P après Ku", width: 92, align: "right", sortable: true, render: (row) => formatPower(row.p_after_ku_w) },
    { key: "ks", label: "Ks", width: 58, align: "right", sortable: true, render: (row) => row.ks ? formatNumber(row.ks) : "—" },
    { key: "p_after_ks_w", label: "P retenue", width: 96, align: "right", sortable: true, render: (row) => <strong className="accent">{formatPower(row.p_after_ks_w)}</strong> },
    { key: "q_after_ks_var", label: "Q retenue", width: 96, align: "right", sortable: true, render: (row) => formatReactivePower(row.q_after_ks_var) },
    { key: "s_after_ks_va", label: "S retenue", width: 92, align: "right", sortable: true, render: (row) => formatApparentPower(row.s_after_ks_va) },
    { key: "currents", label: "Courants L1/L2/L3", width: 150, align: "right", render: (row) => <span className="phase-inline">{formatCurrent(row.current_phases.l1)} / {formatCurrent(row.current_phases.l2)} / {formatCurrent(row.current_phases.l3)}</span> },
    { key: "parent", label: "Tableau", width: 96, render: (row) => <span className="mono">{row.parent_board_id}</span> },
    { key: "status", label: "État", width: 110, render: (row) => <StatusIndicator status={row.status} compact /> },
  ];

  const loadColumns: Array<DataColumn<LoadSummary>> = [
    { key: "id", label: "Référence", width: 96, render: (row) => <span className="mono">{row.id}</span> },
    { key: "designation", label: "Désignation", width: 200, sortable: true, render: (row) => <span className="cell-main">{displayLoad(row).designation}</span> },
    { key: "network", label: "Type", width: 66, sortable: true, render: (row) => <span className="badge badge-outline">{row.network}</span> },
    { key: "quantity", label: "Qté", width: 52, align: "right", sortable: true, render: (row) => row.quantity },
    { key: "voltage_v", label: "Tension", width: 80, align: "right", render: (row) => `${formatNumber(row.voltage_v, 0)} V` },
    { key: "phase", label: "Phase", width: 60, render: (row) => row.phase ?? "—" },
    { key: "installed_power_w", label: "P nominale", width: 96, align: "right", sortable: true, render: (row) => formatPower(row.installed_power_w) },
    { key: "power_factor", label: "Cos φ", width: 66, align: "right", sortable: true, render: (row) => row.power_factor ? formatNumber(row.power_factor) : "—" },
    { key: "ku", label: "Ku", width: 56, align: "right", sortable: true, render: (row) => formatNumber(row.ku) },
    { key: "ks", label: "Ks", width: 56, align: "right", sortable: true, render: (row) => row.ks ? formatNumber(row.ks) : "—" },
    { key: "p_after_ku_w", label: "P après Ku", width: 92, align: "right", sortable: true, render: (row) => formatPower(row.p_after_ku_w) },
    { key: "p_after_ks_w", label: "P retenue", width: 96, align: "right", sortable: true, render: (row) => <strong className="accent">{formatPower(row.p_after_ks_w)}</strong> },
    { key: "q_after_ks_var", label: "Q retenue", width: 96, align: "right", sortable: true, render: (row) => formatReactivePower(row.q_after_ks_var) },
    { key: "s", label: "S", width: 98, align: "right", render: (row) => row.apparent_power_available ? formatApparentPower(row.s_after_ks_va) : <UnitDisplay value={null} unit="kVA" unavailable /> },
    { key: "i", label: "Intensité", width: 88, align: "right", render: (row) => row.current_available ? formatCurrent(row.current_a) : <UnitDisplay value={null} unit="A" unavailable /> },
    { key: "parent", label: "Tableau", width: 96, render: (row) => <span className="mono">{row.parent_board_id}</span> },
    { key: "status", label: "État", width: 110, render: (row) => <StatusIndicator status={row.status} compact /> },
  ];

  const boardColumns: Array<DataColumn<BoardSummary>> = [
    { key: "id", label: "Référence", width: 96, render: (row) => <span className="mono">{row.id}</span> },
    { key: "designation", label: "Désignation", width: 200, sortable: true, render: (row) => <span className="cell-main">{row.designation}</span> },
    { key: "type", label: "Type", width: 90, sortable: true, render: (row) => <span className="badge badge-outline">{row.type}</span> },
    { key: "network", label: "Réseau", width: 68, sortable: true, render: (row) => row.network },
    { key: "voltage", label: "Tension", width: 80, align: "right", render: (row) => `${formatNumber(row.voltage_v, 0)} V` },
    { key: "feeders", label: "Départs", width: 68, align: "right", render: (row) => row.feeder_count },
    { key: "loads", label: "Récepteurs", width: 78, align: "right", render: (row) => row.load_count },
    { key: "p_installed_w", label: "P inst.", width: 90, align: "right", sortable: true, render: (row) => formatPower(row.p_installed_w) },
    { key: "p_after_ku_w", label: "P après Ku", width: 92, align: "right", sortable: true, render: (row) => formatPower(row.p_after_ku_w) },
    { key: "p_after_ks_w", label: "P retenue", width: 96, align: "right", sortable: true, render: (row) => <strong className="accent">{formatPower(row.p_after_ks_w)}</strong> },
    { key: "q_after_ks_var", label: "Q retenue", width: 96, align: "right", sortable: true, render: (row) => formatReactivePower(row.q_after_ks_var) },
    { key: "s_after_ks_va", label: "S retenue", width: 92, align: "right", sortable: true, render: (row) => formatApparentPower(row.s_after_ks_va) },
    { key: "currents", label: "Courants L1/L2/L3", width: 150, align: "right", render: (row) => <span className="phase-inline">{formatCurrent(row.current_phases.l1)} / {formatCurrent(row.current_phases.l2)} / {formatCurrent(row.current_phases.l3)}</span> },
    { key: "unbalance", label: "Déséquilibre", width: 90, align: "right", sortable: true, render: (row) => formatPercent(row.unbalance_percent) },
    { key: "status", label: "État", width: 110, render: (row) => <StatusIndicator status={row.status} compact /> },
  ];

  const handleSort = (key: string) => {
    setSort((current) => current?.key === key
      ? { key, direction: current.direction === "asc" ? "desc" : "asc" }
      : { key, direction: "asc" });
  };

  const handleTreeSelect = (next: Selection) => {
    onSelect(next);
    if (next.kind === "board") setBoardFilter(next.id);
    if (next.kind === "feeder") {
      const feeder = project.feeders.find((item) => item.id === next.id);
      if (feeder) setBoardFilter(feeder.parent_board_id);
    }
    if (next.kind === "load") {
      const load = project.loads.find((item) => item.id === next.id);
      if (load) setBoardFilter(load.parent_board_id);
    }
  };

  const beginPanelResize = (side: "tree" | "property", event: React.PointerEvent) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = side === "tree" ? treeWidth : propertyWidth;
    const move = (moveEvent: PointerEvent) => {
      const delta = side === "tree" ? moveEvent.clientX - startX : startX - moveEvent.clientX;
      const next = Math.max(160, Math.min(420, startWidth + delta));
      if (side === "tree") setTreeWidth(next);
      else setPropertyWidth(next);
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const activeBoard: BoardSummary | null = view === "tgbt" ? null : board;
  const totalPInstalled = activeBoard ? activeBoard.p_installed_w : project.totals.p_installed_w;
  const totalPKu = activeBoard ? activeBoard.p_after_ku_w : project.totals.p_after_ku_w;
  const totalPKs = activeBoard ? activeBoard.p_after_ks_w : project.totals.p_after_ks_w;
  const totalS = activeBoard ? activeBoard.s_after_ks_va : project.totals.s_after_ks_va;
  const totalNeutral = activeBoard ? activeBoard.neutral_current_a : project.totals.neutral_current_a;
  const totalUnbalance = activeBoard ? activeBoard.unbalance_percent : project.totals.unbalance_percent;
  const rows = view === "feeders" ? filteredFeeders : view === "loads" ? filteredLoads : view === "boards" ? filteredBoards : [];
  const rowCount = view === "tgbt" ? 1 : rows.length;
  const selectedFeeder = selection?.kind === "feeder" ? project.feeders.find((item) => item.id === selection.id) ?? null : null;
  const selectedBoard = selection?.kind === "board" ? project.boards.find((item) => item.id === selection.id) ?? null : null;
  const phaseSource = selectedFeeder ?? selectedBoard ?? activeBoard ?? project.boards.find((item) => item.type === "TGBT") ?? null;
  const phaseTitle = selectedFeeder?.designation ?? selectedBoard?.designation ?? activeBoard?.designation ?? "TGBT · projet";
  const phaseData = phaseSource
    ? {
        p: phaseSource.p_phases ?? { l1: null, l2: null, l3: null },
        q: phaseSource.q_phases ?? { l1: null, l2: null, l3: null },
        s: phaseSource.s_phases ?? { l1: null, l2: null, l3: null },
        i: phaseSource.current_phases,
        neutral: phaseSource.neutral_current_a,
        unbalance: phaseSource.unbalance_percent,
      }
    : {
        p: project.totals.p_phases,
        q: project.totals.q_phases,
        s: project.totals.s_phases,
        i: project.totals.current_phases,
        neutral: project.totals.neutral_current_a,
        unbalance: project.totals.unbalance_percent,
      };

  return (
    <div className="page-stack" data-testid="power-balance-screen">
      <PageHeader
        eyebrow="Bilan de puissance · moteur réel"
        title="Le bilan, au centre du travail."
        description="Sélectionnez un tableau ou un départ, filtrez, triez et consultez les résultats du moteur. Aucune formule électrique n’est exécutée dans le navigateur."
        badge={<span className="outline-badge">Moteur local en lecture seule</span>}
      />
      <section className="summary-grid summary-grid-six" aria-label="Synthèse moteur">
        <SummaryCard label="P installée" value={formatPower(totalPInstalled)} detail={activeBoard ? activeBoard.designation : "Projet complet"} icon="bolt" tone="navy" />
        <SummaryCard label="P après Ku" value={formatPower(totalPKu)} detail="Coefficient d’utilisation" icon="balance" tone="navy" />
        <SummaryCard label="P retenue" value={formatPower(totalPKs)} detail="Après Ks · moteur" icon="balance" tone="red" />
        <SummaryCard label="S retenue" value={formatApparentPower(totalS)} detail="Puissance apparente" icon="cpu" tone="navy" />
        <SummaryCard label="Courant neutre" value={formatCurrent(totalNeutral)} detail="Vecteur moteur" icon="bolt" tone="navy" />
        <SummaryCard label="Déséquilibre" value={formatPercent(totalUnbalance)} detail="Indicateur moteur" icon="performance" tone="neutral" />
      </section>

      <div className="balance-workspace" style={{ gridTemplateColumns: `${treeWidth}px 8px minmax(0, 1fr) 8px ${propertyWidth}px` }}>
        <aside className="panel tree-panel" aria-label="Architecture électrique">
          <div className="panel-head"><div><span className="eyebrow">Zone 1</span><h2>Architecture</h2></div><span className="mini-badge">{project.project.board_count} tableaux</span></div>
          <div className="tree-scroll" tabIndex={0} role="region" aria-label="Arborescence du bilan — zone défilante">
            <TreeView
              nodes={tree}
              selection={selection}
              onSelect={handleTreeSelect}
              search={search}
              emptyMessage="Aucun élément ne correspond au filtre."
              ariaLabel="Arborescence du bilan"
            />
          </div>
          <div className="panel-foot"><span className="muted-copy"><Icon name="lock" size={12} /> Données non persistées.</span></div>
        </aside>
        <div className="panel-splitter" role="separator" aria-orientation="vertical" onPointerDown={(event) => beginPanelResize("tree", event)} />
        <section className="panel table-panel" aria-label="Tableau de bilan">
          <div className="panel-head balance-head">
            <Tabs<View>
              label="Vue du bilan"
              active={view}
              onChange={(next) => { setView(next); setSort({ key: "designation", direction: "asc" }); }}
              items={[
                { id: "loads", label: "Récepteurs", count: filteredLoads.length, testId: "balance-tab-loads" },
                { id: "feeders", label: "Départs", count: filteredFeeders.length, testId: "balance-tab-feeders" },
                { id: "boards", label: "Tableaux", count: filteredBoards.length, testId: "balance-tab-boards" },
                { id: "tgbt", label: "TGBT", count: 1, testId: "balance-tab-tgbt" },
              ]}
            />
            <span className="mini-badge">Moteur · {project.engine.version}</span>
          </div>
          <Toolbar
            left={
              <>
                <SearchInput label="Rechercher dans le bilan" value={search} onChange={setSearch} placeholder="Référence, désignation, tableau…" testId="balance-search" />
                <label className="select-control">
                  <span className="sr-only">Filtrer par tableau</span>
                  <Icon name="filter" size={14} />
                  <select value={boardFilter} onChange={(event) => setBoardFilter(event.target.value)} data-testid="balance-board-filter">
                    <option value="all">Tous les tableaux</option>
                    {project.boards.map((item) => <option key={item.id} value={item.id}>{item.designation}</option>)}
                  </select>
                </label>
                <label className="select-control">
                  <span className="sr-only">Filtrer par état</span>
                  <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} data-testid="balance-status-filter">
                    <option value="all">Tous les états</option>
                    {statuses.map((status) => <option key={status} value={status}>{status}</option>)}
                  </select>
                </label>
              </>
            }
            right={
              <>
                <span className="toolbar-count">{rowCount} ligne(s)</span>
                <button type="button" className="button button-ghost button-small" onClick={() => { setSearch(""); setBoardFilter("all"); setStatusFilter("all"); setSort({ key: "designation", direction: "asc" }); }}>
                  <Icon name="reset" size={14} /> Réinitialiser
                </button>
              </>
            }
          />
          <div className="table-scroll-controlled">
            {view === "tgbt" ? (
              <div className="tgbt-summary" data-testid="tgbt-summary">
                <div className="tgbt-metrics">
                  <Metric label="P installée" value={formatPower(project.totals.p_installed_w)} />
                  <Metric label="P après Ku" value={formatPower(project.totals.p_after_ku_w)} />
                  <Metric label="P retenue" value={formatPower(project.totals.p_after_ks_w)} accent />
                  <Metric label="Q retenue" value={formatReactivePower(project.totals.q_after_ks_var)} />
                  <Metric label="S retenue" value={formatApparentPower(project.totals.s_after_ks_va)} />
                  <Metric label="Courant neutre" value={formatCurrent(project.totals.neutral_current_a)} />
                  <Metric label="Déséquilibre" value={formatPercent(project.totals.unbalance_percent)} />
                  <Metric label="Cos φ global" value="Non exposé" unavailable />
                </div>
                <p className="form-note">Synthèse TGBT issue directement du moteur. Le cos φ global n’est pas calculé dans React.</p>
              </div>
            ) : view === "boards" ? (
              <DataTable<BoardSummary>
                key="boards"
                columns={boardColumns}
                rows={filteredBoards}
                rowKey={(row) => row.id}
                selectedKey={selection?.kind === "board" ? selection.id : null}
                onRowClick={(row) => onSelect({ kind: "board", id: row.id })}
                sort={sort}
                onSort={handleSort}
                emptyMessage="Aucun tableau ne correspond aux filtres."
                testId="balance-table"
                rowTestId={(row) => `row-board-${row.id}`}
                ariaLabel="Bilan par tableau"
              />
            ) : view === "feeders" ? (
              <DataTable<FeederSummary>
                key="feeders"
                columns={feederColumns}
                rows={filteredFeeders}
                rowKey={(row) => row.id}
                selectedKey={selection?.kind === "feeder" ? selection.id : null}
                onRowClick={(row) => onSelect({ kind: "feeder", id: row.id })}
                sort={sort}
                onSort={handleSort}
                emptyMessage="Aucun départ ne correspond aux filtres."
                testId="balance-table"
                rowTestId={(row) => `row-${row.id}`}
                ariaLabel="Bilan par départ"
              />
            ) : (
              <DataTable<LoadSummary>
                key="loads"
                columns={loadColumns}
                rows={filteredLoads}
                rowKey={(row) => row.id}
                selectedKey={selection?.kind === "load" ? selection.id : null}
                onRowClick={(row) => onSelect({ kind: "load", id: row.id })}
                sort={sort}
                onSort={handleSort}
                emptyMessage="Aucun récepteur ne correspond aux filtres."
                testId="balance-table"
                rowTestId={(row) => `row-load-${row.id}`}
                rowClassName={(row) => temporaryEdits[row.id]?.designation ? "is-temporary" : ""}
                ariaLabel="Bilan par récepteur"
              />
            )}
          </div>
          <PhaseBalancePanel title={phaseTitle} {...phaseData} />
          <div className="panel-foot">
            <span><Icon name="check" size={13} /> Totaux issus du moteur Python · S/I récepteur issus des contributions après Ku et Ks</span>
            <span>Vue hiérarchique dans l’arborescence · colonnes redimensionnables</span>
          </div>
        </section>
        <div className="panel-splitter" role="separator" aria-orientation="vertical" onPointerDown={(event) => beginPanelResize("property", event)} />
        <aside className="panel inspector-panel" aria-label="Propriétés" tabIndex={0} role="region">
          <PropertyContent
            project={project}
            selection={selection}
            temporaryEdits={temporaryEdits}
            onEditDesignation={onEditDesignation}
            onReset={onReset}
          />
          <CoefficientEditor project={project} selection={selection} onEditCoefficient={onEditCoefficient} />
        </aside>
      </div>
      <div className="balance-insights">
        {previousProject && <ComparisonPanel before={previousProject} after={project} />}
        <TraceabilityPanel project={project} />
      </div>
    </div>
  );
}

function Metric({ label, value, accent = false, unavailable = false }: { label: string; value: string; accent?: boolean; unavailable?: boolean }) {
  return (
    <div className={`tgbt-metric ${accent ? "is-accent" : ""} ${unavailable ? "is-unavailable" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
