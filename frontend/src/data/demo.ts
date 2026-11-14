import type { LoadSummary, ProjectPayload } from "../types";

export type ProjectListItem = {
  id: string;
  name: string;
  reference: string;
  client: string;
  updated: string;
  status: string;
  loads: number;
  boards: number;
  kind: "REAL" | "DEMO";
  note: string;
};

export function projectList(project: ProjectPayload | null): ProjectListItem[] {
  const real: ProjectListItem[] = project
    ? [{
        id: "real",
        name: project.project.name,
        reference: project.project.reference,
        client: project.project.client,
        updated: project.calculated_at,
        status: project.status,
        loads: project.project.load_count,
        boards: project.project.board_count,
        kind: "REAL",
        note: "Fixture réelle · lecture seule",
      }]
    : [];
  return [
    ...real,
    {
      id: "demo-extension",
      name: "Extension atelier — scénario fictif",
      reference: "DEMO-002",
      client: "Client de démonstration",
      updated: "",
      status: "BROUILLON",
      loads: 0,
      boards: 0,
      kind: "DEMO",
      note: "Donnée fictive, non calculée",
    },
    {
      id: "demo-renovation",
      name: "Rénovation tertiaire — scénario fictif",
      reference: "DEMO-003",
      client: "Client de démonstration",
      updated: "",
      status: "ARCHIVE",
      loads: 0,
      boards: 0,
      kind: "DEMO",
      note: "Donnée fictive, non calculée",
    },
  ];
}

export function syntheticLoads(base: LoadSummary[], count: number): LoadSummary[] {
  const source = base.length > 0
    ? base
    : [{
        id: "SYNTH-01",
        designation: "Récepteur synthétique",
        network: "TRI",
        voltage_v: "400",
        nominal_power: "1000",
        power_unit: "W",
        quantity: 1,
        installed_power_w: "1000",
        power_factor: "0.9",
        ku: "1",
        ks: null,
        feeder_id: "SYNTH-FEEDER",
        parent_board_id: "SYNTH-BOARD",
        phase: null,
        p_after_ku_w: "1000",
        q_after_ku_var: "484.322",
        p_after_ks_w: "1000",
        q_after_ks_var: "484.322",
        s_after_ks_va: null,
        current_a: null,
        current_real_a: "1.443",
        current_imag_a: "-0.699",
        current_available: false,
        apparent_power_available: false,
        status: "SYNTHETIC",
        diagnostics: [],
        synthetic: true,
      }];
  return Array.from({ length: count }, (_, index) => {
    const baseLoad = source[index % source.length];
    return {
      ...baseLoad,
      id: `${baseLoad.id}-S${String(index + 1).padStart(4, "0")}`,
      designation: `${baseLoad.designation} · perf ${index + 1}`,
      synthetic: true,
      status: "SYNTHETIC",
      diagnostics: [],
    };
  });
}
