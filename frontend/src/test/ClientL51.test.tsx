import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ClientDialog } from "../components/ClientDialog";

describe("ClientDialog — L5.1", () => {
  it("collecte l'adresse structurée et les coordonnées générales", async () => {
    const onSubmit = vi.fn();
    render(
      <ClientDialog
        open
        mode="create"
        busy={false}
        error={null}
        onSubmit={onSubmit}
        onClose={() => undefined}
      />,
    );
    fireEvent.change(screen.getByTestId("client-company-name"), { target: { value: "Client L5.1" } });
    fireEvent.change(screen.getByTestId("client-address-line1"), { target: { value: "12 rue Neuve" } });
    fireEvent.change(screen.getByTestId("client-address-line2"), { target: { value: "Bâtiment B" } });
    fireEvent.change(screen.getByTestId("client-postal-code"), { target: { value: "75000" } });
    fireEvent.change(screen.getByTestId("client-city"), { target: { value: "Paris" } });
    fireEvent.change(screen.getByTestId("client-country"), { target: { value: "France" } });
    fireEvent.change(screen.getByTestId("client-contact"), { target: { value: "Contact général" } });
    fireEvent.change(screen.getByTestId("client-phone"), { target: { value: "+33 1 11 11 11 11" } });
    fireEvent.change(screen.getByTestId("client-email"), { target: { value: "contact@example.invalid" } });
    fireEvent.click(screen.getByTestId("client-save"));
    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0]).toEqual(
      expect.objectContaining({
        company_name: "Client L5.1",
        address_line1: "12 rue Neuve",
        address_line2: "Bâtiment B",
        postal_code: "75000",
        city: "Paris",
        country: "France",
        contact_name: "Contact général",
        phone: "+33 1 11 11 11 11",
        email: "contact@example.invalid",
      }),
    );
  });

  it("transmet un logo sélectionné et le drapeau de suppression", async () => {
    const onSubmit = vi.fn();
    render(
      <ClientDialog
        open
        mode="create"
        busy={false}
        error={null}
        onSubmit={onSubmit}
        onClose={() => undefined}
      />,
    );
    fireEvent.change(screen.getByTestId("client-company-name"), { target: { value: "Client logo" } });
    const file = new File([new Uint8Array([137, 80, 78, 71])], "logo.png", { type: "image/png" });
    fireEvent.change(screen.getByTestId("client-logo-input"), { target: { files: [file] } });
    fireEvent.click(screen.getByTestId("client-save"));
    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][1]).toBe(file);
    expect(onSubmit.mock.calls[0][2]).toBe(false);
  });
});
