import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { EntityDialog } from "../components/EntityDialog";
import { MoveDuplicateDialog } from "../components/MoveDuplicateDialog";
import { PathDialog } from "../components/PathDialog";
import { ProjectFormDialog } from "../components/ProjectFormDialog";
import { project } from "./fixtures";

describe("composants de gestion de projet", () => {
  it("valide un formulaire de création avec les champs obligatoires", () => {
    const onSubmit = vi.fn();
    render(
      <ProjectFormDialog
        open
        mode="create"
        busy={false}
        error={null}
        onSubmit={onSubmit}
        onClose={() => undefined}
      />,
    );
    fireEvent.change(screen.getByTestId("project-name"), { target: { value: "Projet test" } });
    fireEvent.change(screen.getByTestId("project-reference"), { target: { value: "TEST-01" } });
    fireEvent.change(screen.getByTestId("project-client"), { target: { value: "Client" } });
    fireEvent.click(screen.getByRole("button", { name: "Créer le projet" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      name: "Projet test",
      reference: "TEST-01",
      client: "Client",
      network: "TRI",
    });
  });

  it("construit un récepteur triphasé depuis le formulaire", () => {
    const onSubmit = vi.fn();
    render(
      <EntityDialog
        open
        kind="load"
        mode="create"
        project={project}
        initial={null}
        busy={false}
        error={null}
        onSubmit={onSubmit}
        onClose={() => undefined}
      />,
    );
    fireEvent.change(screen.getByTestId("entity-designation"), { target: { value: "Machine test" } });
    fireEvent.change(screen.getByTestId("entity-network"), { target: { value: "TRI" } });
    fireEvent.change(screen.getByTestId("entity-voltage"), { target: { value: "400" } });
    fireEvent.change(screen.getByTestId("entity-power"), { target: { value: "5000" } });
    fireEvent.change(screen.getByTestId("entity-quantity"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Valider" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      designation: "Machine test",
      network: "TRI",
      voltage_v: "400",
      nominal_power: "5000",
      quantity: 2,
    });
  });

  it("propose une destination de déplacement pour un récepteur", () => {
    const onSubmit = vi.fn();
    render(
      <MoveDuplicateDialog
        open
        action="move"
        kind="load"
        project={project}
        initial={project.loads[0]}
        busy={false}
        error={null}
        onSubmit={onSubmit}
        onClose={() => undefined}
      />,
    );
    fireEvent.change(screen.getByTestId("destination-select"), { target: { value: "DEP-02" } });
    fireEvent.click(screen.getByRole("button", { name: "Déplacer" }));
    expect(onSubmit).toHaveBeenCalledWith({ destination_feeder_id: "DEP-02" });
  });

  it("demande un chemin et une confirmation pour dupliquer", () => {
    const onSubmit = vi.fn();
    render(
      <PathDialog
        open
        mode="duplicate"
        initialPath="D:/qualification/copie.segyrcalc-web.json"
        busy={false}
        error={null}
        onSubmit={onSubmit}
        onClose={() => undefined}
      />,
    );
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Dupliquer" }));
    expect(onSubmit).toHaveBeenCalledWith(
      "D:/qualification/copie.segyrcalc-web.json",
      true,
    );
  });
});
