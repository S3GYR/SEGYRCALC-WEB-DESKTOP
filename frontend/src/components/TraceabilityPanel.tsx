import { shortHash } from "../format";
import { ENGINE_DISPLAY_NAME } from "../presentation";
import type { ProjectPayload } from "../types";

export function TraceabilityPanel({ project }: { project: ProjectPayload }) {
  const checks = project.coherence?.checks ?? [];
  return (
    <details className="trace-panel" data-testid="traceability-panel">
      <summary>
        <span><strong>Traçabilité et cohérence</strong><small>Moteur, révision, hypothèses et contrôles</small></span>
        <span className={`badge ${project.coherence?.status === "PASS" ? "badge-ok" : project.coherence?.status === "FAIL" ? "badge-error" : "badge-warn"}`}>
          {project.coherence?.status ?? "INCONNU"}
        </span>
      </summary>
      <div className="trace-body">
        <dl className="trace-grid">
          <div><dt>Projet</dt><dd className="mono">{project.project.id}</dd></div>
          <div><dt>Moteur</dt><dd>{ENGINE_DISPLAY_NAME}</dd></div>
          <div><dt>Version moteur</dt><dd>{project.engine.version}</dd></div>
          <div><dt>Source</dt><dd className="mono">{shortHash(project.engine.engine_source_sha256, 20)}</dd></div>
          <div><dt>Révision</dt><dd>{project.state.revision}</dd></div>
          <div><dt>Révision calculée</dt><dd>{project.state.calculation_revision ?? "—"}</dd></div>
          <div><dt>Calculé à</dt><dd>{project.calculated_at || "—"}</dd></div>
          <div><dt>Statut</dt><dd>{project.status}</dd></div>
        </dl>
        <div className="trace-checks">
          {checks.map((check) => (
            <div className={`trace-check trace-${check.status.toLowerCase()}`} key={check.id}>
              <strong>{check.label}</strong>
              <span>{check.detail}</span>
              <em>{check.status}</em>
            </div>
          ))}
        </div>
        <div className="trace-notes">
          <strong>Hypothèses moteur</strong>
          <ul>{project.assumptions.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
        {project.diagnostics.length > 0 && (
          <div className="trace-notes">
            <strong>Diagnostics</strong>
            <ul>{project.diagnostics.map((item) => <li key={`${item.code}-${item.message}`}>{item.code} · {item.message}</li>)}</ul>
          </div>
        )}
      </div>
    </details>
  );
}
