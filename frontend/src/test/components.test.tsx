import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { EmptyState } from "../components/EmptyState";
import { StatusIndicator } from "../components/StatusIndicator";
import { Toast } from "../components/Toast";
import { UnitDisplay } from "../components/UnitDisplay";

describe("composants partagés", () => {
  it("affiche un statut avec son libellé", () => {
    render(<StatusIndicator status="OK" />);
    expect(screen.getByText("Conforme")).toBeInTheDocument();
  });

  it("affiche un état vide", () => {
    render(<EmptyState title="Aucune donnée" description="Le tableau est vide." />);
    expect(screen.getByText("Aucune donnée")).toBeInTheDocument();
  });

  it("confirme et annule une action", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<ConfirmDialog open title="Confirmer" message="Message" onConfirm={onConfirm} onCancel={onCancel} />);
    fireEvent.click(screen.getByRole("button", { name: "Annuler" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmer" }));
    expect(onCancel).toHaveBeenCalled();
    expect(onConfirm).toHaveBeenCalled();
  });

  it("ferme une notification", () => {
    const onClose = vi.fn();
    render(<Toast message="Information" onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: "Fermer la notification" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("signale une valeur non exposée", () => {
    render(<UnitDisplay value={null} unit="A" unavailable />);
    expect(screen.getByText("Non exposé")).toBeInTheDocument();
  });
});
