import { useState } from "react";

import packageJson from "../../package.json";
import { PageHeader } from "../components/PageHeader";
import { Icon } from "../icons";
import { ENGINE_DISPLAY_NAME } from "../presentation";

const APP_VERSION = packageJson.version;
const BUILD_ENV = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env ?? {};
const BUILD_ID = BUILD_ENV.VITE_BUILD_ID?.trim() ?? "";
const BUILD_COMMIT = BUILD_ENV.VITE_BUILD_GIT_COMMIT?.trim() ?? "";
const BUILD_AT = BUILD_ENV.VITE_BUILD_AT?.trim() ?? "";
const BUILD_DISTRIBUTION = BUILD_ENV.VITE_BUILD_DISTRIBUTION?.trim() ?? "";

const ABOUT = {
  name: "SEGYRCALC BETA",
  description: "Logiciel de bilan de puissance électrique — version BETA.",
  publisher: "SEGYR Technologies",
  platform: "Windows 11 / Web Desktop",
  environment: "BETA",
  site: "https://segyr-technologies.com",
  copyright: "© 2026 SEGYR Technologies. Tous droits réservés.",
} as const;

function buildDateText(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return `${parsed.toISOString().slice(0, 10)} à ${parsed.toISOString().slice(11, 19)} UTC`;
}

export function AboutScreen({ engineVersion }: { engineVersion: string }) {
  const [copyState, setCopyState] = useState<"technical" | "engine" | "feedback" | null>(null);
  const [copyError, setCopyError] = useState(false);
  const buildDate = BUILD_AT ? buildDateText(BUILD_AT) : "";

  const technicalLines = [
    `Nom : ${ABOUT.name}`,
    `Description : ${ABOUT.description}`,
    `Éditeur : ${ABOUT.publisher}`,
    `Version applicative : ${APP_VERSION}`,
    `Version moteur : ${engineVersion}`,
    `Fonction moteur : ${ENGINE_DISPLAY_NAME}`,
    `Build BETA : ${BUILD_ID || "Non injecté"}`,
  ];
  if (BUILD_COMMIT) {
    technicalLines.push(`Référence Git : ${BUILD_COMMIT}`);
  }
  if (buildDate) {
    technicalLines.push(`Date de build : ${buildDate}`);
  }
  if (BUILD_DISTRIBUTION) {
    technicalLines.push(`Distribution : ${BUILD_DISTRIBUTION}`);
  }
  technicalLines.push(
    `Plateforme : ${ABOUT.platform}`,
    `Environnement : ${ABOUT.environment}`,
    `Site : ${ABOUT.site}`,
    `Copyright : ${ABOUT.copyright}`,
  );
  const technicalText = technicalLines.join("\n");
  const feedbackText = [
    "SEGYRCALC BETA \u2014 Rapport de diagnostic local",
    `Version applicative : ${APP_VERSION}`,
    `Build ID : ${BUILD_ID || "Non inject\u00e9"}`,
    `Commit : ${BUILD_COMMIT || "Non inject\u00e9"}`,
    `Version moteur : ${engineVersion}`,
    `Date du diagnostic : ${new Date().toISOString()}`,
    `Syst\u00e8me : ${navigator.userAgent}`,
    "\u00c9tat : application ouverte",
    "Aucune donn\u00e9e n'est envoy\u00e9e automatiquement.",
    "Ne pas joindre de secrets, de projets complets ou de donn\u00e9es personnelles inutiles.",
  ].join("\n");

  const copyText = async (text: string, kind: "technical" | "engine" | "feedback") => {
    setCopyError(false);
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("Presse-papiers indisponible");
      }
      await navigator.clipboard.writeText(text);
      setCopyState(kind);
    } catch {
      setCopyState(null);
      setCopyError(true);
    }
  };

  return (
    <div className="page-stack about-screen" data-testid="about-screen">
      <PageHeader
        eyebrow="À propos"
        title="À propos de SEGYRCALC BETA"
        description="Informations d'identification et de traçabilité de la version BETA."
        badge={<span className="outline-badge">BETA Windows 11</span>}
      />

      <section className="panel about-hero">
        <img
          src="/assets/segyrcalc-logo.png"
          alt="Logo SEGYRCALC"
          className="about-logo"
        />
        <div className="about-hero-copy">
          <h2>{ABOUT.name}</h2>
          <p>{ABOUT.description}</p>
          <span className="about-publisher">{ABOUT.publisher}</span>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <span className="eyebrow">Traçabilité</span>
            <h2>Informations techniques</h2>
          </div>
          <button
            type="button"
            className="button button-secondary button-small"
            onClick={() => void copyText(technicalText, "technical")}
            data-testid="about-copy-technical"
          >
            <Icon name="check" size={14} /> Copier les informations techniques
          </button>
        </div>
        <dl className="info-list about-info-list">
          <div><dt>Nom</dt><dd>{ABOUT.name}</dd></div>
          <div><dt>Description</dt><dd>{ABOUT.description}</dd></div>
          <div><dt>Éditeur</dt><dd>{ABOUT.publisher}</dd></div>
          <div><dt>Version applicative</dt><dd>{APP_VERSION}</dd></div>
          <div><dt>Version moteur</dt><dd>{engineVersion}</dd></div>
          <div>
            <dt>Moteur</dt>
            <dd className="about-engine-function">
              <span>{ENGINE_DISPLAY_NAME}</span>
              <button
                type="button"
                className="about-inline-copy"
                onClick={() => void copyText(ENGINE_DISPLAY_NAME, "engine")}
                aria-label="Copier le nom du moteur"
                data-testid="about-copy-engine"
              >
                Copier
              </button>
            </dd>
          </div>
          <div><dt>Build BETA</dt><dd className="mono" data-testid="about-build-id">{BUILD_ID || "Non injecté"}</dd></div>
          {BUILD_COMMIT && (
            <div><dt>Référence Git</dt><dd className="mono" data-testid="about-build-commit">{BUILD_COMMIT.slice(0, 12)}</dd></div>
          )}
          {buildDate && (
            <div><dt>Date de build</dt><dd data-testid="about-build-date">{buildDate}</dd></div>
          )}
          {BUILD_DISTRIBUTION && (
            <div><dt>Distribution</dt><dd>{BUILD_DISTRIBUTION}</dd></div>
          )}
          <div><dt>Plateforme</dt><dd>{ABOUT.platform}</dd></div>
          <div><dt>Environnement</dt><dd>{ABOUT.environment}</dd></div>
          <div><dt>Site</dt><dd><a href={ABOUT.site} target="_blank" rel="noreferrer">{ABOUT.site}</a></dd></div>
        </dl>
        {copyState === "technical" && (
          <p className="about-copy-status" role="status" data-testid="about-copy-status">
            Informations techniques copiées.
          </p>
        )}
        {copyState === "engine" && (
          <p className="about-copy-status" role="status" data-testid="about-engine-copy-status">
            Nom du moteur copié.
          </p>
        )}
        {copyError && (
          <p className="about-copy-error" role="alert" data-testid="about-copy-error">
            Copie impossible. Vérifiez l'accès au presse-papiers.
          </p>
        )}
      </section>

      <section className="panel about-feedback" data-testid="about-feedback">
        <div className="panel-head">
          <div>
            <span className="eyebrow">BETA</span>
            <h2>Signaler un problème</h2>
          </div>
          <button
            type="button"
            className="button button-secondary button-small"
            onClick={() => void copyText(feedbackText, "feedback")}
            data-testid="about-copy-feedback"
          >
            <Icon name="check" size={14} /> Copier le rapport de diagnostic
          </button>
        </div>
        <p>
          Préparez un rapport local, vérifiez son contenu, puis transmettez-le
          par le canal de retour convenu avec le responsable de la BETA.
          Aucun envoi automatique vers Internet n'est effectué.
        </p>
        <ol>
          <li>Décrire la fonction testée et les étapes de reproduction.</li>
          <li>Indiquer le résultat attendu et le résultat observé.</li>
          <li>Joindre une capture et, si nécessaire, les journaux locaux.</li>
          <li>Ne jamais joindre de secrets, mots de passe ou projets complets.</li>
        </ol>
        {copyState === "feedback" && (
          <p className="about-copy-status" role="status" data-testid="about-feedback-copy-status">
            Rapport de diagnostic copié.
          </p>
        )}
      </section>

      <footer className="about-footer">
        <p>{ABOUT.copyright}</p>
      </footer>
    </div>
  );
}
