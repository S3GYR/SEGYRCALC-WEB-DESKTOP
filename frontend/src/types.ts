export type Screen =
  | "dashboard"
  | "projects"
  | "clients"
  | "architecture"
  | "balance"
  | "library"
  | "reports"
  | "settings"
  | "about"
  | "engine"
  | "performance";

export type ClientSnapshot = {
  client_id: string | null;
  company_name: string;
  address: string;
  country: string;
  contact_name: string;
  email: string;
  phone: string;
  logo: string | null;
  captured_at: string;
};

export type CompanyProfile = {
  legal_name: string;
  trade_name: string;
  address_line1: string;
  address_line2: string;
  postal_code: string;
  city: string;
  country: string;
  phone: string;
  email: string;
  website: string;
  siren: string;
  siret: string;
  vat_number: string;
  manager_name: string;
  manager_role: string;
  document_footer: string;
  logo: string | null;
};

export type CompanyPayload = {
  company: CompanyProfile;
  configured: boolean;
};

export type Client = {
  id: string;
  company_name: string;
  address: string;
  address_line1?: string;
  address_line2?: string;
  postal_code?: string;
  city?: string;
  formatted_address?: string;
  country: string;
  contact_name: string;
  email: string;
  phone: string;
  logo: string | null;
  has_logo?: boolean;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
};

export type PhaseTriplet = {
  l1: string | null;
  l2: string | null;
  l3: string | null;
};

export type Diagnostic = {
  code: string;
  severity: string;
  message: string;
  field?: string | null;
};

export type BoardSummary = {
  id: string;
  designation: string;
  type: string;
  network: string;
  voltage_v: string;
  parent_feeder_id: string | null;
  phase_voltage_v: string | null;
  has_neutral: boolean;
  p_installed_w: string | null;
  p_after_ku_w: string | null;
  p_after_ks_w: string | null;
  q_after_ku_var: string | null;
  q_after_ks_var: string | null;
  s_after_ku_va: string | null;
  s_after_ks_va: string | null;
  p_phases: PhaseTriplet;
  q_phases: PhaseTriplet;
  s_phases: PhaseTriplet;
  current_phases: PhaseTriplet;
  neutral_current_a: string | null;
  unbalance_percent: string | null;
  status: string;
  feeder_count: number;
  load_count: number;
  diagnostics: Diagnostic[];
};

export type FeederSummary = {
  id: string;
  reference?: string;
  designation: string;
  parent_board_id: string;
  network: string;
  voltage_v: string;
  phase_voltage_v: string | null;
  voltage_ln_v: string | null;
  description: string;
  has_neutral: boolean | null;
  distribution_type?: "MONO_N" | "TRI_NO_N" | "TRI_N";
  phase: string | null;
  ks: string | null;
  member_count: number;
  downstream_board_id: string | null;
  p_installed_w: string | null;
  p_after_ku_w: string | null;
  p_after_ks_w: string | null;
  q_after_ku_var: string | null;
  q_after_ks_var: string | null;
  s_after_ku_va: string | null;
  s_after_ks_va: string | null;
  p_phases: PhaseTriplet;
  q_phases: PhaseTriplet;
  s_phases: PhaseTriplet;
  current_phases: PhaseTriplet;
  neutral_current_a: string | null;
  unbalance_percent: string | null;
  status: string;
  diagnostics: Diagnostic[];
};

export type LoadSummary = {
  id: string;
  designation: string;
  network: string;
  voltage_v: string;
  nominal_power: string;
  power_unit: string;
  quantity: number;
  installed_power_w: string;
  power_factor: string | null;
  ku: string;
  ks: string | null;
  feeder_id: string;
  parent_board_id: string;
  phase: string | null;
  p_after_ku_w: string | null;
  q_after_ku_var: string | null;
  p_after_ks_w: string | null;
  q_after_ks_var: string | null;
  s_after_ks_va: string | null;
  current_a: string | null;
  current_real_a: string | null;
  current_imag_a: string | null;
  current_available: boolean;
  apparent_power_available: boolean;
  status: string;
  diagnostics: Diagnostic[];
  synthetic?: boolean;
};

export type WebMetadata = {
  site: string;
  address: string;
  observations: string;
  created_by: string;
  application: string;
  format_version: string;
};

export type ProjectState = {
  dirty: boolean;
  revision: number;
  calculation_revision: number | null;
  stale: boolean;
  file_path: string | null;
  read_only_source: boolean;
  source_format: string;
  last_error: string | null;
  can_undo: boolean;
  can_redo: boolean;
  undo_label: string | null;
  redo_label: string | null;
  history_length: number;
  undo_depth: number;
  redo_depth: number;
  history_limit: number;
};

export type DeletionPreview = {
  kind: string;
  id: string;
  designation: string;
  boards: number;
  feeders: number;
  loads: number;
  descendants: string[];
  root: boolean;
};

export type SourceType =
  | "AC_THREE_PHASE"
  | "AC_SINGLE_PHASE"
  | "DC"
  | "ENEDIS"
  | "TRANSFORMER"
  | "GENERATOR"
  | "BATTERY";

export type SourcePayload = {
  id: string;
  source_type: SourceType;
  reference: string;
  designation: string;
  quantity: number;
  phase_system: "MONO" | "TRI" | "DC" | null;
  rated_power: string | null;
  rated_power_unit: "KVA" | "VA" | "KW" | "W";
  nominal_voltage: string | null;
  voltage_unit: "V" | "KV";
  frequency_hz: string | null;
  power_factor: string | null;
  primary_voltage: string | null;
  primary_voltage_unit: "V" | "KV";
  secondary_voltage: string | null;
  secondary_voltage_unit: "V" | "KV";
  short_circuit_voltage_percent: string | null;
  coupling: string;
  operating_mode: "SINGLE" | "PARALLEL" | "BACKUP" | "ALTERNATE";
  active_power: string | null;
  active_power_unit: "KVA" | "VA" | "KW" | "W";
  capacity_ah: string | null;
  max_current_a: string | null;
  max_power_w: string | null;
  technology: string;
  connection_type: string;
  subscribed_power_kva: string | null;
  connection_power_kva: string | null;
};

export type ProjectPayload = {
  project: {
    id: string;
    name: string;
    reference: string;
    client: string;
    client_id?: string | null;
    client_snapshot?: ClientSnapshot | null;
    description: string;
    load_count: number;
    board_count: number;
    feeder_count: number;
    unassigned_load_count: number;
  };
  source?: SourcePayload | null;
  format_version?: string;
  engine: {
    source: string;
    facade: string;
    version: string;
    mode: string;
    engine_source_sha256: string;
    fixture: string;
    data_class: string;
  };
  status: string;
  is_calculable: boolean;
  calculated_at: string;
  totals: {
    p_installed_w: string | null;
    p_after_ku_w: string | null;
    p_after_ks_w: string | null;
    q_after_ku_var: string | null;
    q_after_ks_var: string | null;
    s_after_ku_va: string | null;
    s_after_ks_va: string | null;
    p_phases: PhaseTriplet;
    q_phases: PhaseTriplet;
    s_phases: PhaseTriplet;
    current_phases: PhaseTriplet;
    neutral_current_a: string | null;
    unbalance_percent: string | null;
  };
  boards: BoardSummary[];
  feeders: FeederSummary[];
  loads: LoadSummary[];
  /**
   * Additive, optional read-model field. The current backend does not yet
   * emit it; when present it lets the tree/graph expose full unassigned
   * receiver properties instead of inventing placeholder records.
   */
  unassigned_loads?: LoadSummary[];
  diagnostics: Diagnostic[];
  assumptions: string[];
  coherence: CoherenceReport;
  web: WebMetadata;
  state: ProjectState;
};

export type CoherenceCheck = {
  id: string;
  label: string;
  status: "PASS" | "WARN" | "FAIL";
  detail: string;
};

export type CoherenceReport = {
  status: "PASS" | "WARN" | "FAIL";
  checks: CoherenceCheck[];
  orphan_load_ids: string[];
  missing_result_load_ids: string[];
  unassigned_load_ids: string[];
};

export type ProjectFileList = {
  files: ProjectFile[];
  root: string;
};

export type ProjectFile = {
  name: string;
  path: string;
  size: number;
  modified: string;
  writable: boolean;
  format: string;
  client_id?: string | null;
  client_name?: string;
};

export type ProjectProgress = "NOT_DEFINED" | "IN_PROGRESS" | "COMPLETED";

export type ProjectCatalogItem = {
  catalog_id: string;
  project_id: string | null;
  name: string;
  reference: string;
  client_id: string | null;
  client_name: string;
  description: string;
  progress: ProjectProgress;
  created_at: string | null;
  updated_at: string | null;
  file_modified: string;
  format: string;
  writable: boolean;
  metadata_error: string | null;
};

export type ProjectCatalogResponse = {
  items: ProjectCatalogItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};

export type ProjectCatalogQuery = {
  q?: string;
  client_id?: string | null;
  progress?: ProjectProgress | null;
  date_field?: "created" | "updated";
  date_from?: string;
  date_to?: string;
  sort?:
    | "name_asc"
    | "name_desc"
    | "updated_desc"
    | "updated_asc"
    | "created_desc"
    | "created_asc"
    | "client_asc"
    | "client_desc";
  page?: number;
  page_size?: 25 | 50 | 100;
};

export type PowerRequest = {
  mode: "P_KNOWN" | "S_KNOWN";
  network: "MONO" | "TRI";
  voltage_v: string;
  power_value: string;
  power_unit: string;
  power_factor: string;
  power_nature: "ABSORBED" | "USEFUL";
  efficiency: string | null;
};

export type PowerPayload = {
  status: string;
  mode: string;
  network: string;
  power_nature: string;
  p_abs_w: string | null;
  p_useful_w: string | null;
  s_va: string | null;
  q_var: string | null;
  current_a: string | null;
  voltage_v: string | null;
  power_factor: string | null;
  efficiency: string | null;
  diagnostics: Diagnostic[];
  engine: {
    source: string;
    function: string;
    source_sha256: string;
  };
};

export type Selection =
  | { kind: "project"; id: string }
  | { kind: "board"; id: string }
  | { kind: "feeder"; id: string }
  | { kind: "load"; id: string };

export type ReportSectionId =
  | "cover"
  | "general"
  | "summary"
  | "architecture"
  | "boards"
  | "feeders"
  | "receivers"
  | "coefficients"
  | "phases"
  | "assumptions"
  | "traceability";

export type ReportConfig = {
  title: string;
  sections: ReportSectionId[];
  orientation: "portrait" | "landscape";
  decimals: number;
  units: string;
  csv_delimiter: ";" | "," | "\t";
  include_assumptions: boolean;
  include_traceability: boolean;
};

export type ReportSectionOption = { id: ReportSectionId; label: string };

export type ReportOptions = {
  sections: ReportSectionOption[];
  orientations: Array<"portrait" | "landscape">;
  formats: Array<"pdf" | "xlsx" | "csv">;
  export_root: string;
};

export type ReportSnapshotMeta = {
  snapshot_id: string;
  created_at: string;
  project_id: string;
  project_name: string;
  project_reference: string;
  revision: number;
  calculation_revision: number | null;
  source_sha256: string;
  config: ReportConfig;
  engine: ProjectPayload["engine"];
  coherence: CoherenceReport;
};

export type ReportBoardRow = {
  reference: string | null;
  designation: string | null;
  type: string | null;
  network: string | null;
  voltage_v: string | null;
  feeders: number | null;
  receivers: number | null;
  p_installed_w: string | null;
  p_after_ku_w: string | null;
  p_after_ks_w: string | null;
  q_after_ku_var: string | null;
  q_after_ks_var: string | null;
  s_after_ku_va: string | null;
  s_after_ks_va: string | null;
  neutral_current_a: string | null;
  unbalance_percent: string | null;
  status: string | null;
};

export type ReportFeederRow = {
  reference: string | null;
  designation: string | null;
  board: string | null;
  network: string | null;
  voltage_v: string | null;
  receivers: number | null;
  ks: string | null;
  p_installed_w: string | null;
  p_after_ku_w: string | null;
  p_after_ks_w: string | null;
  q_after_ku_var: string | null;
  q_after_ks_var: string | null;
  s_after_ku_va: string | null;
  s_after_ks_va: string | null;
  neutral_current_a: string | null;
  unbalance_percent: string | null;
  status: string | null;
};

export type ReportReceiverRow = {
  reference: string | null;
  designation: string | null;
  board: string | null;
  feeder: string | null;
  network: string | null;
  voltage_v: string | null;
  quantity: number | null;
  installed_power_w: string | null;
  power_factor: string | null;
  ku: string | null;
  ks: string | null;
  p_after_ku_w: string | null;
  p_after_ks_w: string | null;
  q_after_ku_var: string | null;
  q_after_ks_var: string | null;
  s_after_ks_va: string | null;
  current_a: string | null;
  phase: string | null;
  status: string | null;
  s_available: boolean;
  i_available: boolean;
};

export type ReportPreview = {
  snapshot: ReportSnapshotMeta;
  summary: {
    project: ProjectPayload["project"];
    totals: ProjectPayload["totals"];
    status: string;
    is_calculable: boolean;
    calculated_at: string;
  };
  boards: ReportBoardRow[];
  feeders: ReportFeederRow[];
  receivers: ReportReceiverRow[];
  phases: {
    p: PhaseTriplet | null;
    q: PhaseTriplet | null;
    s: PhaseTriplet | null;
    i: PhaseTriplet | null;
    neutral: string | null;
    unbalance: string | null;
  };
  assumptions: string[];
  diagnostics: Diagnostic[];
  coherence: CoherenceReport;
  traceability: {
    engine: ProjectPayload["engine"];
    revision: number;
    calculation_revision: number | null;
    source_sha256: string;
    calculated_at: string;
  };
  config: ReportConfig;
};

export type ReportExportResult = {
  format: "pdf" | "xlsx" | "csv";
  files: Array<{ path: string; bytes: number; sha256?: string }>;
};

export type TemporaryEdits = Record<string, { designation?: string }>;

export type TreeNodeKind = "project" | "board" | "feeder" | "load" | "unassigned-group" | "empty";

export type TreeNode = {
  id: string;
  kind: TreeNodeKind;
  label: string;
  meta: string;
  status: string;
  children?: TreeNode[];
  /** Selection métier explicite. Absent pour les nœuds de présentation. */
  selection?: Selection;
  /** false pour un état vide de présentation, jamais pour un équipement métier. */
  selectable?: boolean;
};
