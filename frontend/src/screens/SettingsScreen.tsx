import { CompanyPanel } from "../components/CompanyPanel";
import { PageHeader } from "../components/PageHeader";
import { SummaryCard } from "../components/SummaryCard";
import { shortHash } from "../format";
import { Icon } from "../icons";
import type { ProjectPayload, Screen } from "../types";

export function SettingsScreen({
  project,
  theme,
  onToggleTheme,
  onNavigate,
  modifiedCount,
  onReset,
}: {
  project: ProjectPayload | null;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onNavigate: (screen: Screen) => void;
  modifiedCount: number;
  onReset: () => void;
}) {
  return (
    <div className="page-stack" data-testid="settings-screen">
      <PageHeader
        eyebrow="Paramètres"
        title="Environnement de qualification"
        description="Configuration locale, identité et contrôles du prototype. Aucune préférence persistante n’est écrite dans un fichier projet."
        badge={<span className="outline-badge">WEB-08 · 0.8.0-r6.2</span>}
      />
      <CompanyPanel />
      <section className="summary-grid summary-grid-compact">
        <SummaryCard label="Thème" value={theme === "light" ? "Clair" : "Sombre"} detail="Préférence de session" icon={theme === "light" ? "sun" : "moon"} tone="navy" />
        <SummaryCard label="Moteur" value={project?.engine.version ?? "—"} detail={project?.engine.facade ?? "Non chargé"} icon="engine" tone="ok" />
        <SummaryCard label="Moteur" value="Lecture seule" detail="Écritures projet via WEB-07" icon="lock" tone="ok" />
        <SummaryCard label="Réseau" value="Hors ligne" detail="Loopback uniquement" icon="offline" tone="neutral" />
      </section>
      <div className="settings-grid">
        <section className="panel">
          <div className="panel-head"><div><span className="eyebrow">Apparence</span><h2>Thème et lisibilité</h2></div></div>
          <div className="settings-row">
            <div><strong>Mode sombre</strong><span>Bascule de session, sans écriture de préférence.</span></div>
            <button
              type="button"
              className={`switch ${theme === "dark" ? "is-on" : ""}`}
              onClick={onToggleTheme}
              aria-pressed={theme === "dark"}
              aria-label={theme === "dark" ? "Désactiver le mode sombre" : "Activer le mode sombre"}
              data-testid="settings-theme-toggle"
            >
              <span />
            </button>
          </div>
          <div className="settings-row">
            <div><strong>Modifications non enregistrées</strong><span>{modifiedCount > 0 ? "Le projet actif doit être enregistré ou fermé sans enregistrer." : "Aucune modification en attente."}</span></div>
            <button type="button" className="button button-ghost button-small" onClick={onReset} disabled={modifiedCount === 0}>
              <Icon name="projects" size={14} /> Gérer le projet
            </button>
          </div>
        </section>
        <section className="panel">
          <div className="panel-head"><div><span className="eyebrow">Moteur</span><h2>Traçabilité</h2></div></div>
          <dl className="info-list">
            <div><dt>Source</dt><dd className="mono">{project?.engine.source ?? "—"}</dd></div>
            <div><dt>Façade</dt><dd className="mono">{project?.engine.facade ?? "—"}</dd></div>
            <div><dt>Empreinte</dt><dd className="mono">{project ? shortHash(project.engine.engine_source_sha256, 24) : "—"}</dd></div>
            <div><dt>Fixture</dt><dd className="mono">recette-business-acceptance-v1.3.json</dd></div>
            <div><dt>Classe</dt><dd>REAL_ENGINE_FIXTURE</dd></div>
          </dl>
        </section>
        <section className="panel">
          <div className="panel-head"><div><span className="eyebrow">Sécurité locale</span><h2>Contrôles actifs</h2></div></div>
          <ul className="check-list">
            <li><Icon name="check" /> Bind 127.0.0.1 et port éphémère</li>
            <li><Icon name="check" /> Jeton de session et contrôle d’origine</li>
            <li><Icon name="check" /> CSP, nosniff et X-Frame-Options</li>
            <li><Icon name="check" /> OpenAPI désactivé</li>
            <li><Icon name="check" /> Aucun CDN, aucune télémétrie</li>
            <li><Icon name="alert" /> Loopback non suffisant pour la production</li>
          </ul>
        </section>
        <section className="panel">
          <div className="panel-head"><div><span className="eyebrow">Qualification</span><h2>Outils de mesure</h2></div></div>
          <div className="settings-links">
            <button type="button" className="quick-item" onClick={() => onNavigate("engine")}>
              <span className="quick-icon"><Icon name="engine" /></span>
              <span><strong>Qualification moteur</strong><small>Calcul B3-01 réel et gestion d’erreur</small></span>
              <Icon name="chevron" size={15} />
            </button>
            <button type="button" className="quick-item" onClick={() => onNavigate("performance")}>
              <span className="quick-icon"><Icon name="performance" /></span>
              <span><strong>Performance UI</strong><small>15, 100, 500 et 1 000 lignes</small></span>
              <Icon name="chevron" size={15} />
            </button>
            <button type="button" className="quick-item" onClick={() => onNavigate("about")} data-testid="settings-about">
              <span className="quick-icon"><Icon name="settings" /></span>
              <span><strong>À propos de SEGYRCALC</strong><small>Versions, éditeur et informations techniques</small></span>
              <Icon name="chevron" size={15} />
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
