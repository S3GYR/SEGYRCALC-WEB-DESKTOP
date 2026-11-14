import { useEffect, useMemo, useRef, useState } from "react";
import { DataTable, type DataColumn, type SortState } from "../components/DataTable";
import { PageHeader } from "../components/PageHeader";
import { SearchInput } from "../components/SearchInput";
import { SummaryCard } from "../components/SummaryCard";
import { Tabs } from "../components/Tabs";
import { syntheticLoads } from "../data/demo";
import { compareNumeric, compareText, formatNumber, formatPower } from "../format";
import { Icon } from "../icons";
import type { LoadSummary, ProjectPayload } from "../types";

type Count = "15" | "100" | "500" | "1000";

type Metrics = {
  render: number | null;
  search: number | null;
  sort: number | null;
  filter: number | null;
};

const counts: Count[] = ["15", "100", "500", "1000"];

export function PerformanceScreen({ project }: { project: ProjectPayload }) {
  const [count, setCount] = useState<Count>("100");
  const [search, setSearch] = useState("");
  const [network, setNetwork] = useState("all");
  const [sort, setSort] = useState<SortState>({ key: "designation", direction: "asc" });
  const [metrics, setMetrics] = useState<Metrics>({ render: null, search: null, sort: null, filter: null });
  const pending = useRef<{ key: keyof Metrics; start: number } | null>(null);
  const rows = useMemo(() => syntheticLoads(project.loads, Number(count)), [project.loads, count]);

  useEffect(() => {
    if (!pending.current) return;
    const { key, start } = pending.current;
    pending.current = null;
    setMetrics((current) => ({ ...current, [key]: performance.now() - start }));
  }, [rows, search, network, sort]);

  const begin = (key: keyof Metrics) => {
    pending.current = { key, start: performance.now() };
  };

  const filtered = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase("fr");
    const selected = rows.filter((row) => {
      if (network !== "all" && row.network !== network) return false;
      return !needle || `${row.id} ${row.designation}`.toLocaleLowerCase("fr").includes(needle);
    });
    return [...selected].sort((left, right) => {
      const comparison = sort.key === "installed_power_w"
        ? compareNumeric(left.installed_power_w, right.installed_power_w)
        : compareText(String(left[sort.key as keyof LoadSummary] ?? ""), String(right[sort.key as keyof LoadSummary] ?? ""));
      return sort.direction === "asc" ? comparison : -comparison;
    });
  }, [rows, search, network, sort]);

  const columns: Array<DataColumn<LoadSummary>> = [
    { key: "id", label: "Référence", width: 130, render: (row) => <span className="mono">{row.id}</span> },
    { key: "designation", label: "Désignation synthétique", width: 260, sortable: true, render: (row) => row.designation },
    { key: "network", label: "Type", width: 70, render: (row) => row.network },
    { key: "quantity", label: "Qté", width: 54, align: "right", render: (row) => row.quantity },
    { key: "installed_power_w", label: "P nominale", width: 105, align: "right", sortable: true, render: (row) => formatPower(row.installed_power_w) },
    { key: "power_factor", label: "Cos φ", width: 70, align: "right", render: (row) => formatNumber(row.power_factor) },
    { key: "ku", label: "Ku", width: 58, align: "right", render: (row) => formatNumber(row.ku) },
    { key: "status", label: "État", width: 100, render: () => <span className="badge badge-synthetic">Synthétique</span> },
  ];

  const memory = (performance as Performance & { memory?: { usedJSHeapSize: number } }).memory;
  const metricCards: Array<[keyof Metrics, string]> = [
    ["render", "Rendu"],
    ["search", "Recherche"],
    ["sort", "Tri"],
    ["filter", "Filtre"],
  ];

  return (
    <div className="page-stack" data-testid="performance-screen">
      <PageHeader
        eyebrow="Qualification UI"
        title="Performance des tableaux volumineux."
        description="Mesures de rendu, recherche, tri et filtre sur des lignes synthétiques. Ces volumes ne déclarent aucune capacité du moteur électrique."
        badge={<span className="outline-badge">Objectif UI</span>}
      />
      <div className="notice notice-warning">
        <Icon name="alert" size={16} />
        <span><strong>Jeu synthétique.</strong> Les lignes sont clonées pour mesurer l’interface ; elles ne sont pas des résultats du moteur et ne doivent pas être utilisées comme un bilan.</span>
      </div>
      <section className="summary-grid summary-grid-compact">
        <SummaryCard label="Jeu actif" value={`${filtered.length} / ${rows.length}`} detail="Lignes affichées" icon="performance" tone="navy" />
        <SummaryCard label="Rendu" value={metrics.render === null ? "—" : `${metrics.render.toFixed(1)} ms`} detail="Changement de volume" icon="cpu" tone="navy" />
        <SummaryCard label="Recherche" value={metrics.search === null ? "—" : `${metrics.search.toFixed(1)} ms`} detail="Filtre texte" icon="search" tone="navy" />
        <SummaryCard label="Mémoire JS" value={memory ? `${(memory.usedJSHeapSize / 1024 / 1024).toFixed(1)} Mo` : "Non exposée"} detail="Chromium / WebView2" icon="cpu" tone="neutral" />
      </section>
      <section className="panel">
        <div className="panel-head">
          <Tabs<Count> label="Volume de lignes" active={count} onChange={(next) => { begin("render"); setCount(next); }} items={counts.map((value) => ({ id: value, label: `${value} lignes`, testId: `perf-count-${value}` }))} />
          <span className="mini-badge">Virtualisation au-delà de 200 lignes</span>
        </div>
        <div className="toolbar toolbar-inside">
          <SearchInput label="Recherche performance" value={search} onChange={(value) => { begin("search"); setSearch(value); }} placeholder="Référence ou désignation…" testId="perf-search" />
          <label className="select-control"><span className="sr-only">Filtrer par réseau</span><Icon name="filter" size={14} /><select value={network} onChange={(event) => { begin("filter"); setNetwork(event.target.value); }} data-testid="perf-network"><option value="all">Tous les réseaux</option><option value="TRI">TRI</option><option value="MONO">MONO</option></select></label>
          <button type="button" className="button button-ghost button-small" onClick={() => { begin("sort"); setSort((current) => ({ key: "installed_power_w", direction: current.key === "installed_power_w" && current.direction === "asc" ? "desc" : "asc" })); }} data-testid="perf-sort">
            <Icon name="performance" size={14} /> Trier par P
          </button>
        </div>
        <div className="metric-strip">
          {metricCards.map(([key, label]) => (
            <div key={key} className="metric-chip"><span>{label}</span><strong>{metrics[key] === null ? "—" : `${metrics[key]?.toFixed(1)} ms`}</strong></div>
          ))}
        </div>
        <DataTable<LoadSummary>
          columns={columns}
          rows={filtered}
          rowKey={(row) => row.id}
          sort={sort}
          onSort={(key) => { begin("sort"); setSort((current) => current.key === key ? { key, direction: current.direction === "asc" ? "desc" : "asc" } : { key, direction: "asc" }); }}
          emptyMessage="Aucune ligne synthétique."
          testId="performance-table"
          ariaLabel="Tableau de performance synthétique"
        />
      </section>
    </div>
  );
}
