import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { Icon } from "../icons";

export function LibraryScreen() {
  return (
    <div className="page-stack" data-testid="library-screen">
      <PageHeader
        eyebrow="Bibliothèque"
        title="Récepteurs types et personnalisés"
        description="Le module est identifié mais non opérationnel dans WEB-05. Aucun modèle de récepteur n’est créé ou modifié."
        badge={<span className="outline-badge">Non disponible</span>}
      />
      <div className="panel">
        <EmptyState
          icon="library"
          title="Module prévu pour une mission ultérieure"
          description="La bibliothèque dépend de la validation du modèle de récepteur, de la persistance et des règles d’import/export. Elle n’est pas simulée dans ce prototype."
        />
      </div>
      <section className="panel">
        <div className="panel-head"><div><span className="eyebrow">Périmètre prévu</span><h2>À qualifier avant développement</h2></div></div>
        <ul className="check-list">
          <li><Icon name="alert" /> Modèle de récepteur type à valider</li>
          <li><Icon name="alert" /> Recherche et familles à spécifier</li>
          <li><Icon name="alert" /> Import/export à définir sans migration destructive</li>
          <li><Icon name="alert" /> Aucun moteur électrique parallèle</li>
        </ul>
      </section>
    </div>
  );
}
