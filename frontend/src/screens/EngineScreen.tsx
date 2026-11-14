import { useEffect, useRef, useState } from "react";
import { calculatePower } from "../api";
import { PageHeader } from "../components/PageHeader";
import { StatusIndicator } from "../components/StatusIndicator";
import { ErrorState } from "../components/ErrorState";
import { NumericInput } from "../components/NumericInput";
import { formatApparentPower, formatCurrent, formatNumber, formatPower, formatReactivePower, shortHash } from "../format";
import { Icon } from "../icons";
import type { PowerPayload, PowerRequest } from "../types";

const initialForm: PowerRequest = {
  mode: "P_KNOWN",
  network: "TRI",
  voltage_v: "400",
  power_value: "8000",
  power_unit: "W",
  power_factor: "0.8",
  power_nature: "ABSORBED",
  efficiency: null,
};

export function EngineScreen() {
  const [form, setForm] = useState<PowerRequest>(initialForm);
  const [result, setResult] = useState<PowerPayload | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const autoRan = useRef(false);

  const update = <K extends keyof PowerRequest>(key: K, value: PowerRequest[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const run = async (override?: Partial<PowerRequest>) => {
    setBusy(true);
    setError(null);
    try {
      setResult(await calculatePower({ ...form, ...override }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Appel local impossible.");
      setResult(null);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (autoRan.current) return;
    const mode = new URLSearchParams(window.location.search).get("run");
    if (mode === "1" || mode === "error") {
      autoRan.current = true;
      void run(mode === "error" ? { power_factor: "1.5" } : undefined);
    }
    // Qualification capture only; no business rule is changed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const units = form.mode === "P_KNOWN" ? ["W", "kW"] : ["VA", "kVA"];

  return (
    <div className="page-stack" data-testid="engine-screen">
      <PageHeader
        eyebrow="Qualification moteur · B3-01"
        title="Le moteur réel, derrière une API locale."
        description="Cette console appelle calculate_power dans le processus Python. Le résultat affiché est produit par le moteur, sans recalcul React."
        badge={<span className="outline-badge">Decimal · 50 chiffres</span>}
      />
      {error && <ErrorState title="Appel local impossible" message={error} onRetry={() => void run()} />}
      <div className="engine-grid">
        <section className="panel">
          <div className="panel-head"><div><span className="eyebrow">Entrées</span><h2>Paramètres du calcul</h2></div><span className="badge badge-outline">{form.mode}</span></div>
          <div className="form-grid">
            <label><span>Mode</span><select value={form.mode} onChange={(event) => {
              const mode = event.target.value as PowerRequest["mode"];
              setForm((current) => ({ ...current, mode, power_unit: mode === "P_KNOWN" ? "W" : "VA" }));
            }} data-testid="engine-mode">
              <option value="P_KNOWN">Puissance active connue</option>
              <option value="S_KNOWN">Puissance apparente connue</option>
            </select></label>
            <label><span>Réseau</span><select value={form.network} onChange={(event) => update("network", event.target.value as PowerRequest["network"])} data-testid="engine-network">
              <option value="TRI">Triphasé équilibré</option>
              <option value="MONO">Monophasé</option>
            </select></label>
            <NumericInput label={form.network === "TRI" ? "Tension composée" : "Tension simple"} value={form.voltage_v} onChange={(value) => update("voltage_v", value)} unit="V" testId="engine-voltage" />
            <label><span>Valeur</span><span className="numeric-control"><input value={form.power_value} onChange={(event) => update("power_value", event.target.value)} inputMode="decimal" data-testid="engine-power" aria-label="Valeur de puissance" /><select value={form.power_unit} onChange={(event) => update("power_unit", event.target.value)} aria-label="Unité de puissance">{units.map((unit) => <option key={unit} value={unit}>{unit}</option>)}</select></span></label>
            <NumericInput label="Facteur de puissance" value={form.power_factor} onChange={(value) => update("power_factor", value)} unit="cos φ" testId="engine-pf" />
            <label><span>Nature</span><select value={form.power_nature} onChange={(event) => update("power_nature", event.target.value as PowerRequest["power_nature"])} data-testid="engine-nature">
              <option value="ABSORBED">Puissance absorbée</option>
              <option value="USEFUL">Puissance utile</option>
            </select></label>
            <NumericInput label="Rendement optionnel" value={form.efficiency ?? ""} onChange={(value) => update("efficiency", value || null)} unit="%" placeholder="0,92" testId="engine-efficiency" />
          </div>
          <div className="form-actions">
            <button type="button" className="button button-primary" onClick={() => void run()} disabled={busy} data-testid="engine-run">
              <Icon name="bolt" size={16} /> {busy ? "Calcul en cours…" : "Calculer avec le moteur"}
            </button>
            <button type="button" className="button button-ghost" onClick={() => void run({ power_factor: "1.5" })} disabled={busy} data-testid="engine-run-error">
              Tester une entrée invalide
            </button>
          </div>
          <p className="form-note">Le moteur n’applique aucun arrondi d’affichage. La présentation arrondit à deux décimales sans modifier la valeur retournée.</p>
        </section>
        <section className="panel results-panel">
          <div className="panel-head"><div><span className="eyebrow">Sorties</span><h2>Résultat du moteur</h2></div>{result && <StatusIndicator status={result.status} />}</div>
          {!result && !error && (
            <div className="empty-result">
              <span className="empty-icon"><Icon name="engine" size={28} /></span>
              <h3>Aucun appel effectué</h3>
              <p>Lancez le calcul pour afficher P, Q, S et I issus du moteur Python.</p>
            </div>
          )}
          {result && (
            <div data-testid="engine-result">
              <div className="result-hero">
                <span>Courant calculé</span>
                <strong>{formatCurrent(result.current_a)}</strong>
                <small>{result.network} · {result.mode} · {formatNumber(result.voltage_v, 0)} V</small>
              </div>
              <div className="result-cards">
                <div className="result-card"><span>P absorbée</span><strong>{formatPower(result.p_abs_w)}</strong></div>
                <div className="result-card"><span>P utile</span><strong>{formatPower(result.p_useful_w)}</strong></div>
                <div className="result-card"><span>Q</span><strong>{formatReactivePower(result.q_var)}</strong></div>
                <div className="result-card"><span>S</span><strong>{formatApparentPower(result.s_va)}</strong></div>
              </div>
              <dl className="result-list engine-meta">
                <div><dt>Statut</dt><dd>{result.status}</dd></div>
                <div><dt>Facteur de puissance</dt><dd>{formatNumber(result.power_factor)}</dd></div>
                <div><dt>Source</dt><dd className="mono">{result.engine.function}</dd></div>
                <div><dt>Empreinte source</dt><dd className="mono">{shortHash(result.engine.source_sha256)}</dd></div>
              </dl>
              <div className="diagnostics-list">
                {result.diagnostics.length === 0
                  ? <div className="diagnostic diagnostic-empty"><Icon name="check" size={13} /><span>Aucun diagnostic.</span></div>
                  : result.diagnostics.map((diagnostic) => (
                    <div key={`${diagnostic.code}-${diagnostic.field ?? ""}`} className={`diagnostic diagnostic-${diagnostic.severity}`}>
                      <Icon name={diagnostic.severity === "error" ? "alert" : "info"} size={13} />
                      <div><strong>{diagnostic.code}</strong><span>{diagnostic.message}</span></div>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
