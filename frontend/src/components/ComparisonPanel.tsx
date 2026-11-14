import { decimalDelta, formatApparentPower, formatCurrent, formatPercent, formatPower, formatReactivePower } from "../format";
import type { ProjectPayload } from "../types";

type Metric = {
  label: string;
  before: string | null;
  after: string | null;
  format: (value: string | null) => string;
};

function deltaText(after: string | null, before: string | null, format: (value: string | null) => string): string {
  const delta = decimalDelta(after, before);
  if (delta === null) return "—";
  return format(delta);
}

export function ComparisonPanel({ before, after }: { before: ProjectPayload; after: ProjectPayload }) {
  const comparable = before.project.id === after.project.id
    && before.state.calculation_revision === before.state.revision
    && after.state.calculation_revision === after.state.revision;
  if (!comparable) {
    return (
      <section className="panel comparison-panel" data-testid="comparison-panel">
        <div className="panel-head"><div><span className="eyebrow">Comparaison</span><h3>Avant / après</h3></div><span className="badge badge-warn">Indisponible</span></div>
        <p className="muted-copy">La comparaison nécessite deux révisions calculées du même projet.</p>
      </section>
    );
  }
  const metrics: Metric[] = [
    { label: "P installée", before: before.totals.p_installed_w, after: after.totals.p_installed_w, format: formatPower },
    { label: "P après Ku", before: before.totals.p_after_ku_w, after: after.totals.p_after_ku_w, format: formatPower },
    { label: "P retenue", before: before.totals.p_after_ks_w, after: after.totals.p_after_ks_w, format: formatPower },
    { label: "Q retenue", before: before.totals.q_after_ks_var, after: after.totals.q_after_ks_var, format: formatReactivePower },
    { label: "S retenue", before: before.totals.s_after_ks_va, after: after.totals.s_after_ks_va, format: formatApparentPower },
    { label: "Courant neutre", before: before.totals.neutral_current_a, after: after.totals.neutral_current_a, format: formatCurrent },
    { label: "Déséquilibre", before: before.totals.unbalance_percent, after: after.totals.unbalance_percent, format: formatPercent },
  ];
  return (
    <section className="panel comparison-panel" data-testid="comparison-panel">
      <div className="panel-head"><div><span className="eyebrow">Comparaison de session</span><h3>Avant / après</h3></div><span className="badge badge-outline">rév. {before.state.revision} → {after.state.revision}</span></div>
      <div className="comparison-grid">
        {metrics.map((metric) => (
          <div className="comparison-row" key={metric.label}>
            <span>{metric.label}</span>
            <b>{metric.format(metric.before)}</b>
            <b className="accent">{metric.format(metric.after)}</b>
            <em>{deltaText(metric.after, metric.before, metric.format)}</em>
          </div>
        ))}
      </div>
      <p className="form-note">Écarts calculés entre deux résultats moteur validés. Aucun résultat périmé n’est comparé.</p>
    </section>
  );
}
