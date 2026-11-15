import { Icon, type IconName } from "../icons";
import type { Screen } from "../types";

type NavItem = { screen: Screen; label: string; icon: IconName; testId: string; soon?: boolean };

const primary: NavItem[] = [
  { screen: "dashboard", label: "Accueil", icon: "dashboard", testId: "nav-dashboard" },
  { screen: "projects", label: "Projets", icon: "projects", testId: "nav-projects" },
  { screen: "clients", label: "Clients", icon: "projects", testId: "nav-clients" },
  { screen: "architecture", label: "Architecture électrique", icon: "tree", testId: "nav-architecture" },
  { screen: "balance", label: "Bilan de puissance", icon: "balance", testId: "nav-balance" },
  { screen: "library", label: "Bibliothèque", icon: "library", testId: "nav-library", soon: true },
  { screen: "reports", label: "Rapports", icon: "report", testId: "nav-reports", soon: true },
  { screen: "settings", label: "Paramètres", icon: "settings", testId: "nav-settings" },
];

const tools: NavItem[] = [
  { screen: "engine", label: "Qualification moteur", icon: "engine", testId: "nav-engine" },
  { screen: "performance", label: "Performance UI", icon: "performance", testId: "nav-performance" },
];

export function Sidebar({
  screen,
  onNavigate,
  projectName,
  modified,
}: {
  screen: Screen;
  onNavigate: (screen: Screen) => void;
  projectName: string;
  modified: boolean;
}) {
  const renderItem = (item: NavItem) => (
    <button
      key={item.testId}
      type="button"
      className={`nav-item ${screen === item.screen ? "is-active" : ""}`}
      onClick={() => onNavigate(item.screen)}
      data-testid={item.testId}
      aria-current={screen === item.screen ? "page" : undefined}
    >
      <Icon name={item.icon} />
      <span>{item.label}</span>
      {item.soon && <span className="soon">Statut</span>}
      {screen === item.screen && <span className="nav-active-mark" />}
    </button>
  );

  return (
    <aside className="sidebar">
      <div className="brand">
        <img src="/assets/segyrcalc-logo.png" alt="" className="brand-logo" />
        <div>
          <div className="brand-name">SEGYRCALC</div>
          <div className="brand-owner">SEGYR Technologies</div>
        </div>
      </div>

      <div className="sidebar-project">
        <span className="eyebrow">Projet actif</span>
        <strong title={projectName}>{projectName}</strong>
        <span className="project-state">
          <span className="dot dot-ok" /> Moteur disponible
        </span>
        {modified && <span className="temporary-badge">Modifications non enregistrées</span>}
      </div>

      <nav className="nav" aria-label="Navigation principale">
        <span className="nav-label">Espace de travail</span>
        {primary.map(renderItem)}
        <span className="nav-label nav-label-spaced">Outils de qualification</span>
        {tools.map(renderItem)}
      </nav>

      <div className="sidebar-foot">
        <div className="offline-card">
          <span className="offline-icon"><Icon name="offline" size={16} /></span>
          <div>
            <strong>100 % hors ligne</strong>
            <span>Aucun CDN · aucun service externe</span>
          </div>
        </div>
        <div className="build-stamp">WEB-08 · 0.8.0-r6.2</div>
      </div>
    </aside>
  );
}
