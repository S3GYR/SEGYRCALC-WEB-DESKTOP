import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createClient } from "../api";
import { ProjectFormDialog } from "../components/ProjectFormDialog";

const client = {
  id: "39438879-7362-419d-8406-2467afcf3ebd",
  company_name: "ETR",
  address: "RUE DE LA PAIE",
  country: "FRANCE",
  contact_name: "VCT",
  email: "",
  phone: "",
  logo: null,
  is_archived: false,
  created_at: "2026-11-10T04:05:39.182971+00:00",
  updated_at: "2026-11-10T04:05:39.182971+00:00",
};

vi.mock("../api", () => ({
  ApiError: class ApiError extends Error {},
  createClient: vi.fn(),
}));

describe("ProjectFormDialog — client", () => {
  it("associe un client existant au projet", () => {
    const onSubmit = vi.fn();
    render(
      <ProjectFormDialog
        open
        mode="create"
        clients={[client]}
        busy={false}
        error={null}
        onSubmit={onSubmit}
        onClose={() => undefined}
      />,
    );
    fireEvent.change(screen.getByTestId("project-name"), { target: { value: "Projet" } });
    fireEvent.change(screen.getByTestId("project-reference"), { target: { value: "REF-01" } });
    fireEvent.change(screen.getByTestId("project-client-select"), {
      target: { value: client.id },
    });
    expect(screen.getByTestId("project-client-summary")).toHaveTextContent("ETR");
    fireEvent.click(screen.getByRole("button", { name: "Créer le projet" }));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        client_id: client.id,
        client: "ETR",
      }),
    );
  });

  it("crée un client depuis le parcours projet et le sélectionne", async () => {
    const onSubmit = vi.fn();
    vi.mocked(createClient).mockResolvedValue({
      ...client,
      id: "00000000-0000-0000-0000-000000000099",
      company_name: "Client créé",
    });
    render(
      <ProjectFormDialog
        open
        mode="create"
        clients={[client]}
        busy={false}
        error={null}
        onSubmit={onSubmit}
        onClose={() => undefined}
      />,
    );
    fireEvent.change(screen.getByTestId("project-name"), { target: { value: "Projet" } });
    fireEvent.change(screen.getByTestId("project-reference"), { target: { value: "REF-01" } });
    fireEvent.click(screen.getByTestId("project-create-client"));
    fireEvent.change(screen.getByTestId("client-company-name"), { target: { value: "Client créé" } });
    fireEvent.click(screen.getByTestId("client-save"));
    await waitFor(() => expect(createClient).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId("project-client-summary")).toHaveTextContent("Client créé"));
    fireEvent.click(screen.getByRole("button", { name: "Créer le projet" }));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        client_id: "00000000-0000-0000-0000-000000000099",
        client: "Client créé",
      }),
    );
  });
});
