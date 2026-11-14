import { formatApparentPower, formatCurrent, formatPercent, formatPower, formatReactivePower } from "../format";
import type { PhaseTriplet } from "../types";

export function PhaseBalancePanel({
  title,
  p,
  q,
  s,
  i,
  neutral,
  unbalance,
}: {
  title: string;
  p: PhaseTriplet;
  q: PhaseTriplet;
  s: PhaseTriplet;
  i: PhaseTriplet;
  neutral: string | null;
  unbalance: string | null;
}) {
  const phases = [
    { name: "L1", p: p.l1, q: q.l1, s: s.l1, i: i.l1 },
    { name: "L2", p: p.l2, q: q.l2, s: s.l2, i: i.l2 },
    { name: "L3", p: p.l3, q: q.l3, s: s.l3, i: i.l3 },
  ];
  const available = phases.some((phase) => phase.p !== null || phase.i !== null);
  return (
    <div className="phase-panel" data-testid="phase-balance-panel">
      <div className="panel-head"><div><span className="eyebrow">Phases</span><h3>{title}</h3></div><span className={`badge ${available ? "badge-ok" : "badge-neutral"}`}>{available ? "Calculé" : "Non exposé"}</span></div>
      <div className="phase-grid">
        {phases.map((phase) => (
          <div className="phase-card" key={phase.name}>
            <strong>{phase.name}</strong>
            <span>P <b>{formatPower(phase.p)}</b></span>
            <span>Q <b>{formatReactivePower(phase.q)}</b></span>
            <span>S <b>{formatApparentPower(phase.s)}</b></span>
            <span>I <b>{formatCurrent(phase.i)}</b></span>
          </div>
        ))}
      </div>
      <div className="phase-foot">
        <span>Neutre <b>{formatCurrent(neutral)}</b></span>
        <span>Déséquilibre <b>{formatPercent(unbalance)}</b></span>
        <span className="muted-copy">Valeurs moteur · aucune répartition recalculée dans React</span>
      </div>
    </div>
  );
}
