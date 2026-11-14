import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { DataTable, type DataColumn } from "../components/DataTable";

type Row = { id: string; name: string; value: string };

const columns: Array<DataColumn<Row>> = [
  { key: "id", label: "Référence", width: 100, render: (row) => row.id },
  { key: "name", label: "Nom", sortable: true, render: (row) => row.name },
  { key: "value", label: "Valeur", align: "right", render: (row) => row.value },
];

const rows: Row[] = [
  { id: "A", name: "Alpha", value: "10" },
  { id: "B", name: "Bêta", value: "20" },
];

describe("DataTable", () => {
  it("affiche les lignes et les en-têtes", () => {
    render(<DataTable columns={columns} rows={rows} rowKey={(row) => row.id} emptyMessage="Vide" ariaLabel="Test" />);
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Bêta")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Nom/ })).toBeInTheDocument();
  });

  it("sélectionne une ligne au clic et au clavier", () => {
    const onRowClick = vi.fn();
    render(<DataTable columns={columns} rows={rows} rowKey={(row) => row.id} onRowClick={onRowClick} emptyMessage="Vide" ariaLabel="Test" />);
    fireEvent.click(screen.getByText("Alpha"));
    expect(onRowClick).toHaveBeenCalledWith(rows[0]);
    const row = screen.getByText("Alpha").closest("tr")!;
    fireEvent.keyDown(row, { key: "Enter" });
    expect(onRowClick).toHaveBeenCalledTimes(2);
  });

  it("affiche l’état vide", () => {
    render(<DataTable columns={columns} rows={[]} rowKey={(row) => row.id} emptyMessage="Aucune ligne" ariaLabel="Test" />);
    expect(screen.getByText("Aucune ligne")).toBeInTheDocument();
  });

  it("déclenche le tri par colonne", () => {
    const onSort = vi.fn();
    render(<DataTable columns={columns} rows={rows} rowKey={(row) => row.id} onSort={onSort} emptyMessage="Vide" ariaLabel="Test" />);
    fireEvent.click(screen.getByTestId("sort-name"));
    expect(onSort).toHaveBeenCalledWith("name");
  });

  it("virtualise les jeux volumineux", () => {
    const many = Array.from({ length: 1000 }, (_, index) => ({ id: `R${index}`, name: `Ligne ${index}`, value: String(index) }));
    render(<DataTable columns={columns} rows={many} rowKey={(row) => row.id} emptyMessage="Vide" ariaLabel="Test" />);
    expect(screen.getByText(/Virtualisation active/)).toBeInTheDocument();
    expect(screen.getAllByRole("row").length).toBeLessThan(100);
  });
});
