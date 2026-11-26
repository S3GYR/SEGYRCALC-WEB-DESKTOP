import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../components/CompanyPanel", () => ({
  CompanyPanel: () => null,
}));

import packageJson from "../../package.json";
import { AboutScreen } from "../screens/AboutScreen";
import { SettingsScreen } from "../screens/SettingsScreen";

const ENGINE_VERSION = "1.3.0";
const ENGINE_FACADE = "calcelect.service_v13.calculate_project_v13";
const ENGINE_DISPLAY_NAME = "SEGYRCALC \u2013 Moteur de calcul \u00e9lectrique";

function renderAbout() {
  return render(
    <AboutScreen engineVersion={ENGINE_VERSION} />,
  );
}

beforeEach(() => {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
});

describe("À propos de SEGYRCALC BETA", () => {
  it("affiche l'identité, les versions et le logo officiel", () => {
    const { container } = renderAbout();

    expect(screen.getByTestId("about-screen")).toBeInTheDocument();
    expect(screen.getByAltText("Logo SEGYRCALC")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "À propos de SEGYRCALC BETA" })).toBeInTheDocument();
    expect(screen.getAllByText("Logiciel de bilan de puissance électrique — version BETA.").length).toBeGreaterThan(0);
    expect(screen.getAllByText("SEGYR Technologies").length).toBeGreaterThan(0);
    expect(screen.getByText("0.9.0-beta.2")).toBeInTheDocument();
    expect(packageJson.version).toBe("0.9.0-beta.2");
    expect(screen.getByText("1.3.0")).toBeInTheDocument();
    expect(screen.getByText(ENGINE_DISPLAY_NAME)).toBeInTheDocument();
    expect(screen.queryByText(ENGINE_FACADE)).not.toBeInTheDocument();
    expect(screen.getByText("Windows 11 / Web Desktop")).toBeInTheDocument();
    expect(screen.getAllByText("BETA").length).toBeGreaterThan(0);
    expect(screen.getByText("https://segyr-technologies.com")).toBeInTheDocument();
    expect(screen.getByText("© 2026 SEGYR Technologies. Tous droits réservés.")).toBeInTheDocument();

    expect(screen.getByTestId("about-build-id")).toHaveTextContent("Non injecté");
    expect(screen.queryByTestId("about-build-date")).not.toBeInTheDocument();
    expect(container.querySelector("footer.about-footer")).toBeInTheDocument();
    expect(container.querySelector("footer.about-footer")).not.toHaveClass("panel");
  });

  it("présente le nom du moteur avec bouton de copie", () => {
    renderAbout();
    expect(screen.getByText(ENGINE_DISPLAY_NAME)).toBeInTheDocument();
    expect(screen.getByTestId("about-copy-engine")).toHaveAttribute(
      "aria-label",
      "Copier le nom du moteur",
    );
  });

  it("prépare un rapport de diagnostic BETA local", async () => {
    renderAbout();
    fireEvent.click(screen.getByTestId("about-copy-feedback"));

    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(1));
    const copied = String(vi.mocked(navigator.clipboard.writeText).mock.calls[0][0]);
    expect(copied).toContain("SEGYRCALC BETA");
    expect(copied).toContain("Version applicative : 0.9.0-beta.2");
    expect(copied).toContain("Version moteur : 1.3.0");
    expect(copied).not.toContain(ENGINE_FACADE);
    expect(copied).toContain("Aucune donnée n'est envoyée automatiquement.");
    expect(screen.getByTestId("about-feedback-copy-status")).toBeInTheDocument();
  });

  it("copie les informations techniques sans chemin absolu", async () => {
    renderAbout();

    fireEvent.click(screen.getByTestId("about-copy-technical"));

    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(1));
    const copied = String(vi.mocked(navigator.clipboard.writeText).mock.calls[0][0]);
    expect(copied).toContain("Version applicative : 0.9.0-beta.2");
    expect(copied).toContain("Version moteur : 1.3.0");
    expect(copied).toContain(`Fonction moteur : ${ENGINE_DISPLAY_NAME}`);
    expect(copied).not.toContain(ENGINE_FACADE);
    expect(copied).toContain("Build BETA : Non injecté");
    expect(copied).toContain("Environnement : BETA");
    expect(copied).not.toMatch(/[A-Za-z]:\\/);
    expect(screen.getByTestId("about-copy-status")).toBeInTheDocument();
  });

  it("copie uniquement le nom du moteur depuis son bouton dédié", async () => {
    renderAbout();
    fireEvent.click(screen.getByTestId("about-copy-engine"));

    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(1));
    expect(vi.mocked(navigator.clipboard.writeText).mock.calls[0][0]).toBe(ENGINE_DISPLAY_NAME);
    expect(screen.getByTestId("about-engine-copy-status")).toBeInTheDocument();
  });

  it("ne confirme pas une copie technique en échec", async () => {
    vi.mocked(navigator.clipboard.writeText).mockRejectedValueOnce(new Error("refus"));
    renderAbout();
    fireEvent.click(screen.getByTestId("about-copy-technical"));

    await waitFor(() => expect(screen.getByTestId("about-copy-error")).toBeInTheDocument());
    expect(screen.queryByTestId("about-copy-status")).not.toBeInTheDocument();
  });

  it("reste lisible sous thème sombre", () => {
    document.documentElement.dataset.theme = "dark";
    renderAbout();
    expect(screen.getByTestId("about-screen")).toBeInTheDocument();
    document.documentElement.dataset.theme = "light";
  });

  it("est accessible depuis les Paramètres", () => {
    const onNavigate = vi.fn();
    render(
      <SettingsScreen
        project={null}
        theme="light"
        onToggleTheme={() => undefined}
        onNavigate={onNavigate}
        modifiedCount={0}
        onReset={() => undefined}
      />,
    );

    fireEvent.click(screen.getByTestId("settings-about"));
    expect(onNavigate).toHaveBeenCalledWith("about");
  });
});
