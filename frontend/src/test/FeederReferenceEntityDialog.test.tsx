import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EntityDialog } from "../components/EntityDialog";
import { project } from "./fixtures";

describe("EntityDialog - repère automatique", () => {
  it("préremplit Q1 et envoie repère et désignation séparés", () => {
    const onSubmit = vi.fn();
    render(
      <EntityDialog
        open
        kind="feeder"
        mode="create"
        project={project}
        initial={null}
        busy={false}
        error={null}
        onSubmit={onSubmit}
        onClose={() => undefined}
      />,
    );
    expect(screen.getByTestId("entity-reference")).toHaveValue("Q1");
    fireEvent.change(screen.getByTestId("entity-reference"), { target: { value: "Q9" } });
    fireEvent.change(screen.getByTestId("entity-designation"), { target: { value: "Éclairage RDC" } });
    fireEvent.click(screen.getByRole("button", { name: "Valider" }));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        reference: "Q9",
        auto_reference: false,
        designation: "Éclairage RDC",
      }),
    );
  });
});
