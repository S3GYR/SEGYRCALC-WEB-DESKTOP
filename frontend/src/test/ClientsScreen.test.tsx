import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  listClients: vi.fn(),
  createClient: vi.fn(),
  updateClient: vi.fn(),
  archiveClient: vi.fn(),
  reactivateClient: vi.fn(),
}));

vi.mock("../api", () => ({
  ApiError: class ApiError extends Error {},
  ...mocks,
}));

import { ClientsScreen } from "../screens/ClientsScreen";

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

const created = {
  ...client,
  id: "00000000-0000-0000-0000-000000000099",
  company_name: "Nouveau client",
  contact_name: "Marie",
};

describe("ClientsScreen", () => {
  it("liste les clients et crée une fiche", async () => {
    const onToast = vi.fn();
    mocks.listClients.mockResolvedValue({ clients: [client] });
    mocks.createClient.mockResolvedValue(created);
    render(<ClientsScreen onToast={onToast} />);
    expect(await screen.findByText("ETR")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("client-new"));
    fireEvent.change(screen.getByTestId("client-company-name"), {
      target: { value: "Nouveau client" },
    });
    fireEvent.change(screen.getByTestId("client-contact"), { target: { value: "Marie" } });
    fireEvent.click(screen.getByTestId("client-save"));

    await waitFor(() =>
      expect(mocks.createClient).toHaveBeenCalledWith(
        expect.objectContaining({
          company_name: "Nouveau client",
          contact_name: "Marie",
        }),
      ),
    );
    expect(await screen.findByTestId(`client-row-${created.id}`)).toHaveTextContent("Nouveau client");
    expect(onToast).toHaveBeenCalledWith("Client créé.", "success");
  });

  it("filtre la liste et propose l’édition", async () => {
    mocks.listClients.mockResolvedValue({ clients: [client] });
    render(<ClientsScreen onToast={vi.fn()} />);
    expect(await screen.findByText("ETR")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("client-search"), { target: { value: "absent" } });
    expect(await screen.findByText("Aucun résultat")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("client-search"), { target: { value: "ETR" } });
    expect(await screen.findByText("ETR")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId(`client-edit-${client.id}`));
    expect(screen.getByTestId("client-dialog")).toBeInTheDocument();
  });
});
