import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, exportReport, loadReportOptions, previewReport } from "../api";
import { ExportPathDialog } from "../components/ExportPathDialog";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { SummaryCard } from "../components/SummaryCard";
import {
  chooseExportFile,
  chooseExportFolder,
  hasNativeExportDialog,
} from "../desktop";
import {
  formatApparentPower,
  formatCurrent,
  formatNumber,
  formatPercent,
  formatPower,
  formatReactivePower,
  shortDate,
  shortHash,
} from "../format";
import { Icon } from "../icons";
import type {
  ProjectPayload,
  ReportConfig,
  ReportExportResult,
  ReportOptions,
  ReportPreview,
  ReportSectionId,
} from "../types";

const DEFAULT_SECTIONS: ReportSectionId[] = [
  "cover",
  "general",
  "summary",
  "architecture",
  "boards",
  "feeders",
  "receivers",
  "coefficients",
  "phases",
  "assumptions",
  "traceability",
];

const DEFAULT_OPTIONS: ReportOptions = {
  sections: [
    { id: "cover", label: "Page de garde" },
    { id: "general", label: "Informations générales" },
    { id: "summary", label: "Synthèse générale TGBT" },
    { id: "architecture", label: "Architecture électrique" },
    { id: "boards", label: "Synthèses des tableaux" },
    { id: "feeders", label: "Bilan des départs" },
    { id: "receivers", label: "Bilan des récepteurs" },
    { id: "coefficients", label: "Coefficients Ku et Ks" },
    { id: "phases", label: "Répartition des phases" },
    { id: "assumptions", label: "Hypothèses et limites" },
    { id: "traceability", label: "Traçabilité" },
  ],
  orientations: ["portrait", "landscape"],
  formats: ["pdf", "xlsx", "csv"],
  export_root: "",
};

function defaultConfig(project: ProjectPayload | null): ReportConfig {
  return {
    title: project ? `Bilan de puissance — ${project.project.name}` : "Bilan de puissance électrique",
    sections: DEFAULT_SECTIONS,
    orientation: "portrait",
    decimals: 2,
    units: "auto",
    csv_delimiter: ";",
    include_assumptions: true,
    include_traceability: true,
  };
}

function safeName(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[^\w-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 60) || "projet";
}

function joinPath(root: string, name: string): string {
  if (!root) return name;
  const separator = root.includes("\\") ? "\\" : "/";
  return `${root.replace(/[\\/]+$/, "")}${separator}${name}`;
}

function cell(value: ReactNode, exact?: string | null): ReactNode {
  return <span title={exact ?? (typeof value === "string" ? value : undefined)}>{value}</span>;
}

function PreviewTable({
  headers,
  rows,
  testId,
}: {
  headers: string[];
  rows: ReactNode[][];
  testId: string;
}) {
  return (
    <div className="report-table-wrap">
      <table className="report-table" data-testid={testId}>
        <thead>
          <tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>{row.map((value, column) => <td key={column}>{value}</td>)}</tr>
          ))}
          {rows.length === 0 && (
            <tr><td colSpan={headers.length} className="report-empty">Aucune ligne dans cette section.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function valueOrUnavailable(value: string | null | undefined, formatter: (item: string | null | undefined) => string): string {
  return value === null || value === undefined || value === "" ? "Non exposé" : formatter(value);
}

export function ReportsScreen({
  project,
  onNotify,
}: {
  project: ProjectPayload | null;
  onNotify?: (message: string, tone: "info" | "success" | "warning" | "error") => void;
}) {
  const [options, setOptions] = useState<ReportOptions>(DEFAULT_OPTIONS);
  const [config, setConfig] = useState<ReportConfig>(() => defaultConfig(project));
  const [preview, setPreview] = useState<ReportPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [exportDialog, setExportDialog] = useState<{ format: "pdf" | "xlsx" | "csv"; initialPath: string } | null>(null);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportResult, setExportResult] = useState<ReportExportResult | null>(null);

  useEffect(() => {
    loadReportOptions()
      .then((loaded) => setOptions(loaded))
      .catch(() => setOptions(DEFAULT_OPTIONS));
  }, []);

  useEffect(() => {
    setPreview(null);
    setExportResult(null);
    setError(null);
    setMessage(null);
    setExportDialog(null);
  }, [project?.project.id, project?.state.revision]);

  useEffect(() => {
    setConfig((current) => {
      const previousAutomatic = current.title === "Bilan de puissance électrique"
        || current.title.startsWith("Bilan de puissance — ");
      if (!previousAutomatic) return current;
      return { ...current, title: defaultConfig(project).title };
    });
  }, [project?.project.id, project?.project.name]);

  const stale = Boolean(project && (project.state.stale || project.state.calculation_revision !== project.state.revision));
  const reference = project ? safeName(project.project.reference) : "projet";
  const revision = project?.state.revision ?? 0;
  const baseName = `rapport-${reference}-rev${revision}`;

  const defaultPath = (format: "pdf" | "xlsx" | "csv"): string => {
    const root = options.export_root;
    if (format === "csv") return joinPath(root, `csv-${reference}-rev${revision}`);
    return joinPath(root, `${baseName}.${format}`);
  };

  const notify = (text: string, tone: "info" | "success" | "warning" | "error") => {
    setMessage(text);
    onNotify?.(text, tone);
  };

  const generate = async () => {
    if (!project || stale) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    setExportResult(null);
    try {
      const loaded = await previewReport(config);
      setPreview(loaded);
      notify(`Aperçu généré depuis le snapshot ${shortHash(loaded.snapshot.snapshot_id)}.`, "success");
    } catch (caught) {
      const text = caught instanceof Error ? caught.message : "Génération de l’aperçu impossible.";
      setError(text);
      notify(text, "error");
    } finally {
      setBusy(false);
    }
  };

  const runExport = async (format: "pdf" | "xlsx" | "csv", path: string, overwrite: boolean) => {
    if (!preview) return;
    setExportBusy(true);
    setExportError(null);
    try {
      const result = await exportReport(preview.snapshot.snapshot_id, format, path, overwrite);
      setExportResult(result);
      setExportDialog(null);
      notify(
        `Export ${format.toUpperCase()} terminé : ${result.files.length} fichier${result.files.length > 1 ? "s" : ""}.`,
        "success",
      );
    } catch (caught) {
      const text = caught instanceof Error ? caught.message : "Export impossible.";
      setExportError(text);
      if (!(caught instanceof ApiError && caught.code === "FICHIER_EXISTE")) {
        notify(text, "error");
      }
    } finally {
      setExportBusy(false);
    }
  };

  const startExport = async (format: "pdf" | "xlsx" | "csv") => {
    if (!preview) return;
    if (hasNativeExportDialog(format)) {
      const selected = format === "csv"
        ? await chooseExportFolder(`csv-${reference}-rev${revision}`)
        : await chooseExportFile(format, `${baseName}.${format}`);
      if (!selected) return;
      // The native Windows Save dialog already owns the overwrite prompt.
      // CSV folder selection does not prompt per file, so it stays protected.
      await runExport(format, selected, format !== "csv");
      return;
    }
    setExportError(null);
    setExportDialog({ format, initialPath: defaultPath(format) });
  };

  const toggleSection = (section: ReportSectionId) => {
    setConfig((current) => ({
      ...current,
      sections: current.sections.includes(section)
        ? current.sections.filter((item) => item !== section)
        : [...current.sections, section],
    }));
    setPreview(null);
  };

  const summaryCards = useMemo(() => {
    if (!preview) return [];
    const totals = preview.summary.totals;
    return [
      { label: "Puissance installée", value: formatPower(totals.p_installed_w), detail: "Moteur · projet", icon: "balance" as const, tone: "navy" as const },
      { label: "Puissance après Ku", value: formatPower(totals.p_after_ku_w), detail: "Moteur · après coefficients", icon: "chart" as const, tone: "navy" as const },
      { label: "Puissance retenue", value: formatPower(totals.p_after_ks_w), detail: "Moteur · après Ks", icon: "shield" as const, tone: "red" as const },
      { label: "Puissance apparente", value: formatApparentPower(totals.s_after_ks_va), detail: "Moteur · S retenue", icon: "bolt" as const, tone: "neutral" as const },
      { label: "Courant neutre", value: formatCurrent(totals.neutral_current_a), detail: "Moteur · phases", icon: "activity" as const, tone: "warn" as const },
      { label: "Déséquilibre", value: formatPercent(totals.unbalance_percent), detail: "Moteur · phases", icon: "alert" as const, tone: "warn" as const },
    ];
  }, [preview]);

  return (
    <div className="page-stack reports-page" data-testid="reports-screen">
      <PageHeader
        eyebrow="Rapports"
        title="Synthèses et exports techniques"
        description="Compagnon local de production PDF, Excel et CSV à partir des résultats électriques validés."
        badge={<span className={preview ? "status-pill status-ok" : "outline-badge"}>{preview ? "Snapshot prêt" : "Aperçu requis"}</span>}
      />

      {!project && (
        <div className="panel">
          <EmptyState
            icon="report"
            title="Aucun projet ouvert"
            description="Ouvrez ou créez un projet WEB-03/WEB-06 pour générer un rapport depuis ses résultats moteur."
          />
        </div>
      )}

      {project && (
        <div className="report-workspace">
          <section className="panel report-config-panel" aria-label="Configuration du rapport">
            <div className="panel-head">
              <div>
                <span className="eyebrow">Configuration</span>
                <h2>Paramètres du document</h2>
              </div>
              <span className="mono report-rev">rév. {revision}</span>
            </div>
            <div className="report-config-grid">
              <label className="path-field">
                <span>Titre du document</span>
                <input
                  value={config.title}
                  onChange={(event) => { setConfig({ ...config, title: event.target.value }); setPreview(null); }}
                  data-testid="report-config-title"
                  maxLength={200}
                />
              </label>
              <div className="report-config-row">
                <label className="path-field">
                  <span>Orientation</span>
                  <select
                    value={config.orientation}
                    onChange={(event) => { setConfig({ ...config, orientation: event.target.value as ReportConfig["orientation"] }); setPreview(null); }}
                    data-testid="report-orientation"
                  >
                    <option value="portrait">Portrait A4</option>
                    <option value="landscape">Paysage A4</option>
                  </select>
                </label>
                <label className="path-field">
                  <span>Décimales</span>
                  <select
                    value={config.decimals}
                    onChange={(event) => { setConfig({ ...config, decimals: Number(event.target.value) }); setPreview(null); }}
                    data-testid="report-decimals"
                  >
                    {[0, 1, 2, 3, 4, 5, 6].map((value) => <option key={value} value={value}>{value}</option>)}
                  </select>
                </label>
              </div>
              <label className="path-field">
                <span>Séparateur CSV</span>
                <select
                  value={config.csv_delimiter}
                  onChange={(event) => { setConfig({ ...config, csv_delimiter: event.target.value as ReportConfig["csv_delimiter"] }); setPreview(null); }}
                  data-testid="report-csv-delimiter"
                >
                  <option value=";">Point-virgule (;)</option>
                  <option value=",">Virgule (,)</option>
                  <option value={"\t"}>Tabulation</option>
                </select>
              </label>
              <div>
                <span className="report-label">Sections incluses</span>
                <div className="report-sections">
                  {options.sections.map((section) => (
                    <label key={section.id} className="checkbox-label report-section-option">
                      <input
                        type="checkbox"
                        checked={config.sections.includes(section.id)}
                        onChange={() => toggleSection(section.id)}
                        data-testid={`report-section-${section.id}`}
                      />
                      {section.label}
                    </label>
                  ))}
                </div>
              </div>
              <div className="report-config-row">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={config.include_assumptions}
                    onChange={(event) => { setConfig({ ...config, include_assumptions: event.target.checked }); setPreview(null); }}
                  />
                  Inclure les hypothèses
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={config.include_traceability}
                    onChange={(event) => { setConfig({ ...config, include_traceability: event.target.checked }); setPreview(null); }}
                  />
                  Inclure la traçabilité
                </label>
              </div>
            </div>

            {stale && (
              <div className="inline-alert inline-alert-warning" data-testid="report-stale">
                Le résultat courant n’est pas calculé pour la révision active. Recalculez le projet avant de générer un rapport.
              </div>
            )}
            {error && <div className="inline-alert inline-alert-error" role="alert">{error}</div>}
            {message && !error && <div className="inline-alert inline-alert-info">{message}</div>}

            <div className="report-actions">
              <button
                type="button"
                className="button button-primary"
                onClick={() => void generate()}
                disabled={busy || stale}
                data-testid="report-preview-generate"
              >
                <Icon name="report" size={15} /> {busy ? "Génération…" : "Générer l’aperçu"}
              </button>
              {!options.export_root && <span className="report-note">Répertoire d’export isolé indisponible.</span>}
            </div>

            <div className="report-export-block">
              <div className="panel-head report-export-head">
                <div><span className="eyebrow">Exports</span><h2>Depuis le snapshot</h2></div>
              </div>
              <p className="report-note">
                PDF multipage, classeur Excel structuré et six fichiers CSV. Aucun recalcul métier ; les valeurs proviennent du snapshot.
              </p>
              <div className="report-export-buttons">
                <button type="button" className="button button-secondary" disabled={!preview || exportBusy} onClick={() => void startExport("pdf")} data-testid="report-export-pdf">
                  <Icon name="file" size={15} /> PDF
                </button>
                <button type="button" className="button button-secondary" disabled={!preview || exportBusy} onClick={() => void startExport("xlsx")} data-testid="report-export-xlsx">
                  <Icon name="chart" size={15} /> Excel
                </button>
                <button type="button" className="button button-secondary" disabled={!preview || exportBusy} onClick={() => void startExport("csv")} data-testid="report-export-csv">
                  <Icon name="download" size={15} /> CSV
                </button>
              </div>
              {exportError && <div className="inline-alert inline-alert-error" role="alert">{exportError}</div>}
              {exportResult && (
                <div className="report-export-result" data-testid="report-export-result">
                  <strong>Export {exportResult.format.toUpperCase()} terminé</strong>
                  <ul>
                    {exportResult.files.map((file) => (
                      <li key={file.path}><span className="mono">{file.path}</span> · {formatNumber(String(file.bytes / 1024), 1)} Ko</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </section>

          <section className="panel report-preview-panel" aria-label="Aperçu du rapport">
            <div className="panel-head">
              <div>
                <span className="eyebrow">Aperçu</span>
                <h2>Contenu du snapshot</h2>
              </div>
              {preview && <span className="status-pill status-ok" data-testid="report-snapshot">{shortHash(preview.snapshot.snapshot_id, 12)}</span>}
            </div>
            {!preview ? (
              <EmptyState
                icon="report"
                title="Aperçu non généré"
                description="Choisissez les sections, puis générez l’aperçu. L’aperçu et les trois exports partagent le même snapshot figé."
              />
            ) : (
              <div className="report-preview" data-testid="report-preview">
                <div className="report-preview-meta">
                  <div><span>Projet</span><strong>{preview.snapshot.project_name}</strong></div>
                  <div><span>Référence</span><strong>{preview.snapshot.project_reference || "—"}</strong></div>
                  <div><span>Révision</span><strong>{preview.snapshot.revision} / calculée {preview.snapshot.calculation_revision ?? "—"}</strong></div>
                  <div><span>Empreinte</span><strong className="mono">{shortHash(preview.snapshot.source_sha256, 20)}</strong></div>
                  <div><span>Cohérence</span><strong className={`status-text status-${preview.coherence.status.toLowerCase()}`}>{preview.coherence.status}</strong></div>
                  <div><span>Généré</span><strong>{shortDate(preview.snapshot.created_at)}</strong></div>
                </div>

                <div className="summary-grid report-summary-grid">
                  {summaryCards.map((card) => <SummaryCard key={card.label} {...card} />)}
                </div>

                <p className="report-note report-preview-note">
                  Aperçu structuré fondé sur le snapshot. La pagination exacte et les en-têtes répétés sont produits par le moteur PDF.
                  Les valeurs affichées sont formatées ; les valeurs exactes restent dans le snapshot et les exports.
                </p>

                <div className="report-section">
                  <h3>Synthèse TGBT</h3>
                  <PreviewTable
                    testId="report-table-boards"
                    headers={["Réf.", "Désignation", "Type", "P installée", "P Ku", "P retenue", "S retenue", "Déséquilibre", "État"]}
                    rows={preview.boards.map((item) => [
                      cell(item.reference),
                      cell(item.designation),
                      cell(item.type),
                      cell(formatPower(item.p_installed_w), item.p_installed_w),
                      cell(formatPower(item.p_after_ku_w), item.p_after_ku_w),
                      cell(formatPower(item.p_after_ks_w), item.p_after_ks_w),
                      cell(formatApparentPower(item.s_after_ks_va), item.s_after_ks_va),
                      cell(formatPercent(item.unbalance_percent), item.unbalance_percent),
                      cell(item.status),
                    ])}
                  />
                </div>

                <div className="report-section">
                  <h3>Bilan des départs</h3>
                  <PreviewTable
                    testId="report-table-feeders"
                    headers={["Réf.", "Désignation", "Tableau", "Ks", "P retenue", "Q retenue", "S retenue", "État"]}
                    rows={preview.feeders.map((item) => [
                      cell(item.reference),
                      cell(item.designation),
                      cell(item.board),
                      cell(item.ks),
                      cell(formatPower(item.p_after_ks_w), item.p_after_ks_w),
                      cell(formatReactivePower(item.q_after_ks_var), item.q_after_ks_var),
                      cell(formatApparentPower(item.s_after_ks_va), item.s_after_ks_va),
                      cell(item.status),
                    ])}
                  />
                </div>

                <div className="report-section">
                  <h3>Bilan des récepteurs</h3>
                  <PreviewTable
                    testId="report-table-receivers"
                    headers={["Réf.", "Désignation", "Départ", "Type", "Qté", "Ku", "Ks", "P retenue", "Q retenue", "S", "I", "Phase", "État"]}
                    rows={preview.receivers.slice(0, 200).map((item) => [
                      cell(item.reference),
                      cell(item.designation),
                      cell(item.feeder),
                      cell(item.network),
                      cell(item.quantity),
                      cell(item.ku),
                      cell(item.ks),
                      cell(formatPower(item.p_after_ks_w), item.p_after_ks_w),
                      cell(formatReactivePower(item.q_after_ks_var), item.q_after_ks_var),
                      cell(item.s_available ? formatApparentPower(item.s_after_ks_va) : "Non exposé", item.s_after_ks_va),
                      cell(item.i_available ? formatCurrent(item.current_a) : "Non exposé", item.current_a),
                      cell(item.phase),
                      cell(item.status),
                    ])}
                  />
                  {preview.receivers.length > 200 && (
                    <p className="report-note">Affichage limité aux 200 premières lignes ; le PDF, le XLSX et le CSV contiennent les {preview.receivers.length} récepteurs.</p>
                  )}
                </div>

                <div className="report-section report-phase-preview">
                  <h3>Phases et déséquilibre</h3>
                  <PreviewTable
                    testId="report-table-phases"
                    headers={["Phase", "P", "Q", "S", "I"]}
                    rows={(["l1", "l2", "l3"] as const).map((phase) => [
                      phase.toUpperCase(),
                      cell(formatPower(preview.phases.p?.[phase]), preview.phases.p?.[phase]),
                      cell(formatReactivePower(preview.phases.q?.[phase]), preview.phases.q?.[phase]),
                      cell(formatApparentPower(preview.phases.s?.[phase]), preview.phases.s?.[phase]),
                      cell(formatCurrent(preview.phases.i?.[phase]), preview.phases.i?.[phase]),
                    ])}
                  />
                  <p className="report-note">
                    Neutre : {valueOrUnavailable(preview.phases.neutral, formatCurrent)} · Déséquilibre : {valueOrUnavailable(preview.phases.unbalance, formatPercent)}.
                    Les S/I individuels récepteur sont issus des contributions moteur après Ku et Ks. Le cos φ global reste non exposé.
                  </p>
                </div>

                <div className="report-section report-trace-preview">
                  <h3>Traçabilité</h3>
                  <dl className="report-trace-grid">
                    <div><dt>Moteur</dt><dd>{preview.traceability.engine.facade}</dd></div>
                    <div><dt>Version</dt><dd>{preview.traceability.engine.version}</dd></div>
                    <div><dt>Source moteur</dt><dd className="mono">{shortHash(preview.traceability.engine.engine_source_sha256, 24)}</dd></div>
                    <div><dt>Empreinte snapshot</dt><dd className="mono">{shortHash(preview.snapshot.source_sha256, 24)}</dd></div>
                    <div><dt>Calcul</dt><dd>{preview.summary.calculated_at ? shortDate(preview.summary.calculated_at) : "—"}</dd></div>
                    <div><dt>Version rapport</dt><dd>WEB-06 / 1</dd></div>
                  </dl>
                </div>
              </div>
            )}
          </section>
        </div>
      )}

      {exportDialog && (
        <ExportPathDialog
          open
          format={exportDialog.format}
          initialPath={exportDialog.initialPath}
          root={options.export_root}
          busy={exportBusy}
          error={exportError}
          onSubmit={(path, overwrite) => void runExport(exportDialog.format, path, overwrite)}
          onClose={() => { setExportDialog(null); setExportError(null); }}
        />
      )}
    </div>
  );
}
