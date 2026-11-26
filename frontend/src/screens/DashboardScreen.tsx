import { formatPower, shortDate } from "../format";
import { Icon } from "../icons";
import { projectList } from "../data/demo";
import type { ProjectPayload, Screen } from "../types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusIndicator } from "../components/StatusIndicator";
import { SummaryCard } from "../components/SummaryCard";
import { ENGINE_DISPLAY_NAME } from "../presentation";

export function DashboardScreen({
  project,
  loading,
  error,
  onNavigate,
}: {
  project: ProjectPayload | null;
  loading: boolean;
  error: string | null;
  onNavigate: (screen: Screen) => void;
}) {
  if (error) {
    return <EmptyState icon="alert" title="Tableau de bord indisponible" description={error} />;
  }
  if (loading) {
    return <EmptyState icon="cpu" title="Chargement du projet" description="Le moteur local est sollicité en lecture seule." />;
  }
  if (!project) {
    return <EmptyState icon="projects" title="Aucun projet chargé" description="Le prototype n'a pas reçu de fixture projet." />;
  }
  const rows = projectList(project);

  return (
    <div className="page-stack" data-testid="dashboard-screen">
      <PageHeader
        eyebrow="Accueil · environnement d’étude"
        title="Bonjour, votre espace de travail est prêt."
        description="Préparez, contrôlez et expliquez les bilans électriques dans une interface web Windows, sans jamais réécrire les moteurs existants."
        badge={<span className="outline-badge">Qualification WEB-07</span>}
        actions={
          <>
            <button type="button" className="button button-secondary" onClick={() => onNavigate("architecture")}>
              <Icon name="tree" size={16} /> Architecture
            </button>
            <button type="button" className="button button-primary" onClick={() => onNavigate("balance")}>
              <Icon name="balance" size={16} /> Ouvrir le bilan
            </button>
          </>
        }
      />

      <div className="notice notice-info">
        <Icon name="info" size={16} />
        <span>
          <strong>Mode lecture seule.</strong> Les projets, les moteurs et les formats existants ne sont pas modifiés.
          Les modifications sont enregistrées via l'espace Projets.
        </span>
      </div>

      <section className="summary-grid" aria-label="Indicateurs du projet">
        <SummaryCard
          label="Projet actif"
          value={project.project.reference}
          detail={project.project.name}
          icon="file"
          tone="navy"
          testId="kpi-project"
        />
        <SummaryCard
          label="Puissance installée"
          value={formatPower(project.totals.p_installed_w)}
          detail={`${project.project.load_count} récepteurs · ${project.project.board_count} tableaux`}
          icon="bolt"
          tone="navy"
        />
        <SummaryCard
          label="Puissance retenue"
          value={formatPower(project.totals.p_after_ks_w)}
          detail="Après Ku et Ks, valeurs du moteur"
          icon="balance"
          tone="red"
        />
        <SummaryCard
          label="État du moteur"
          value={project.status === "OK" ? "Conforme" : project.status}
          detail={`${shortDate(project.calculated_at)} · ${project.engine.version}`}
          icon="shield"
          tone={project.status === "OK" ? "ok" : "warn"}
        />
      </section>

      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-head">
            <div><span className="eyebrow">Projets</span><h2>Reprendre le travail</h2></div>
            <span className="demo-badge">Réel + démonstration</span>
          </div>
          <div className="table-wrap">
            <table className="simple-table">
              <thead><tr><th>Projet</th><th>Référence</th><th>Activité</th><th>État</th><th /></tr></thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className={row.kind === "DEMO" ? "is-muted" : ""}>
                    <td>
                      <div className="cell-main">{row.name}</div>
                      <div className="cell-sub">{row.note}</div>
                    </td>
                    <td className="mono">{row.reference}</td>
                    <td>{row.updated ? shortDate(row.updated) : "—"}</td>
                    <td>
                      {row.kind === "REAL"
                        ? <StatusIndicator status={row.status} compact />
                        : <span className="badge badge-neutral">{row.status === "BROUILLON" ? "Brouillon" : "Archivé"}</span>}
                    </td>
                    <td className="cell-action">
                      <button
                        type="button"
                        className="text-button"
                        disabled={row.kind !== "REAL"}
                        onClick={() => onNavigate("balance")}
                      >
                        Ouvrir <Icon name="arrow" size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="panel-foot">
            <button type="button" className="button button-ghost" onClick={() => onNavigate("projects")}>
              <Icon name="projects" size={15} /> Nouveau / ouvrir un projet
            </button>
            <button type="button" className="button button-ghost" onClick={() => onNavigate("projects")}>
              Enregistrer / gérer les fichiers
            </button>
          </div>
        </section>

        <section className="panel">
          <div className="panel-head"><div><span className="eyebrow">Accès rapides</span><h2>Espace de travail</h2></div></div>
          <div className="quick-list">
            <button type="button" className="quick-item" onClick={() => onNavigate("architecture")}>
              <span className="quick-icon"><Icon name="tree" /></span>
              <span><strong>Architecture électrique</strong><small>Explorer TGBT, tableaux et départs</small></span>
              <Icon name="chevron" size={15} />
            </button>
            <button type="button" className="quick-item" onClick={() => onNavigate("balance")}>
              <span className="quick-icon"><Icon name="balance" /></span>
              <span><strong>Bilan de puissance</strong><small>Tableau, recherche, tri et propriétés</small></span>
              <Icon name="chevron" size={15} />
            </button>
            <button type="button" className="quick-item" onClick={() => onNavigate("engine")}>
              <span className="quick-icon"><Icon name="engine" /></span>
              <span><strong>Qualification moteur</strong><small>Appeler une fonction réelle du cœur</small></span>
              <Icon name="chevron" size={15} />
            </button>
            <button type="button" className="quick-item" onClick={() => onNavigate("performance")}>
              <span className="quick-icon"><Icon name="performance" /></span>
              <span><strong>Performance UI</strong><small>15, 100, 500 et 1 000 lignes</small></span>
              <Icon name="chevron" size={15} />
            </button>
          </div>
        </section>
      </div>

      <div className="dashboard-grid dashboard-grid-bottom">
        <section className="panel">
          <div className="panel-head"><div><span className="eyebrow">Moteur</span><h2>Autorité de calcul</h2></div><span className="outline-badge">Lecture seule</span></div>
          <dl className="info-list">
            <div><dt>Moteur de calcul</dt><dd>{ENGINE_DISPLAY_NAME}</dd></div>
            <div><dt>Contrat B3-01</dt><dd className="mono">calculate_power</dd></div>
            <div><dt>Version moteur</dt><dd>{project.engine.version}</dd></div>
            <div><dt>Empreinte source</dt><dd className="mono">{project.engine.engine_source_sha256.slice(0, 16)}…</dd></div>
            <div><dt>Jeu de données</dt><dd className="mono">V1.3 · fixture réelle</dd></div>
          </dl>
        </section>
        <section className="panel">
          <div className="panel-head"><div><span className="eyebrow">Périmètre WEB-07</span><h2>Ce qui est réellement disponible</h2></div></div>
          <ul className="check-list">
            <li><Icon name="check" /> Navigation, arborescence et tableau interactifs</li>
            <li><Icon name="check" /> Recherche, tri, filtre et sélection</li>
            <li><Icon name="check" /> Propriétés et modifications persistantes</li>
            <li><Icon name="check" /> Résultats issus du moteur Python</li>
            <li><Icon name="check" /> Création, ouverture, édition et sauvegarde locale</li>
            <li><Icon name="alert" /> Bibliothèque et rapports : non opérationnels</li>
          </ul>
        </section>
      </div>
    </div>
  );
}
