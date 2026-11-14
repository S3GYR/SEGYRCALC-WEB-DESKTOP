import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getCompany: vi.fn(),
  updateCompany: vi.fn(),
  uploadCompanyLogo: vi.fn(),
  deleteCompanyLogo: vi.fn(),
  fetchCompanyLogo: vi.fn(),
}));

vi.mock("../api", () => ({
  ApiError: class ApiError extends Error {},
  ...mocks,
}));

import { CompanyPanel } from "../components/CompanyPanel";

const empty = {
  configured: false,
  company: {
    legal_name: "",
    trade_name: "",
    address_line1: "",
    address_line2: "",
    postal_code: "",
    city: "",
    country: "",
    phone: "",
    email: "",
    website: "",
    siren: "",
    siret: "",
    vat_number: "",
    manager_name: "",
    manager_role: "",
    document_footer: "",
    logo: null,
  },
};

const configured = {
  configured: true,
  company: {
    ...empty.company,
    legal_name: "ACME Énergie",
    address_line1: "12 rue de l'Électricité",
    postal_code: "75000",
    city: "Paris",
    country: "France",
    phone: "+33 1 23 45 67 89",
    email: "contact@acme.example",
  },
};

describe("CompanyPanel — L5.3", () => {
  it("affiche l'absence de profil sans imposer d'identité", async () => {
    mocks.getCompany.mockResolvedValue(empty);
    render(<CompanyPanel />);
    expect(await screen.findByTestId("company-panel")).toBeInTheDocument();
    expect(await screen.findByText(/Entreprise non configurée/)).toBeInTheDocument();
    expect(screen.getByTestId("company-edit")).toHaveTextContent("Configurer mon entreprise");
    expect(screen.queryByText("SEGYR Technologies")).not.toBeInTheDocument();
  });

  it("crée un profil entreprise avec adresse et coordonnées", async () => {
    mocks.getCompany.mockResolvedValue(empty);
    mocks.updateCompany.mockResolvedValue(configured);
    render(<CompanyPanel />);
    await screen.findByText(/Entreprise non configurée/);
    fireEvent.click(screen.getByTestId("company-edit"));
    fireEvent.change(screen.getByTestId("company-legal-name"), {
      target: { value: "ACME Énergie" },
    });
    fireEvent.change(screen.getByTestId("company-address-line1"), {
      target: { value: "12 rue de l'Électricité" },
    });
    fireEvent.change(screen.getByTestId("company-postal-code"), { target: { value: "75000" } });
    fireEvent.change(screen.getByTestId("company-city"), { target: { value: "Paris" } });
    fireEvent.change(screen.getByTestId("company-country"), { target: { value: "France" } });
    fireEvent.change(screen.getByTestId("company-email"), {
      target: { value: "contact@acme.example" },
    });
    fireEvent.click(screen.getByTestId("company-save"));
    await waitFor(() => expect(mocks.updateCompany).toHaveBeenCalled());
    expect(mocks.updateCompany.mock.calls[0][0]).toEqual(
      expect.objectContaining({
        legal_name: "ACME Énergie",
        address_line1: "12 rue de l'Électricité",
        postal_code: "75000",
        city: "Paris",
        country: "France",
        email: "contact@acme.example",
      }),
    );
    expect(await screen.findByText("ACME Énergie")).toBeInTheDocument();
  });

  it("affiche un profil configuré avec ses informations légales", async () => {
    mocks.getCompany.mockResolvedValue(configured);
    render(<CompanyPanel />);
    expect(await screen.findByText("ACME Énergie")).toBeInTheDocument();
    expect(screen.getByText("SIRET")).toBeInTheDocument();
    expect(screen.getByText("TVA intracommunautaire")).toBeInTheDocument();
    expect(screen.getByTestId("company-edit")).toHaveTextContent("Modifier");
  });
});
