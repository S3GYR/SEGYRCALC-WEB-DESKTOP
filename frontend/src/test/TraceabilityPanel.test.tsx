import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TraceabilityPanel } from "../components/TraceabilityPanel";
import { ENGINE_DISPLAY_NAME } from "../presentation";
import { project } from "./fixtures";

describe("TraceabilityPanel engine branding", () => {
  it("shows the user-facing engine name and keeps the internal facade hidden", () => {
    render(<TraceabilityPanel project={project} />);
    expect(screen.getByText(ENGINE_DISPLAY_NAME)).toBeInTheDocument();
    expect(screen.getByText(project.engine.version)).toBeInTheDocument();
    expect(screen.queryByText(project.engine.facade)).not.toBeInTheDocument();
  });
});
