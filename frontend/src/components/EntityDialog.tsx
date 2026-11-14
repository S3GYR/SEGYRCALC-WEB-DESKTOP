import { useEffect, useState } from "react";
import { FormModal } from "./FormModal";
import {
  allowedDistributionTypes,
  defaultDistributionType,
  distributionFromFeeder,
  distributionSummary,
  DISTRIBUTION_LABELS,
  type DistributionType,
} from "../data/distribution";
import { feederLabel, nextFeederReference } from "../data/feederReference";
import type { BoardSummary, FeederSummary, LoadSummary, ProjectPayload } from "../types";

type EntityKind = "board" | "feeder" | "load";
type EntityMode = "create" | "edit";

type FormState = {
  parent_board_id: string;
  reference: string;
  reference_auto: boolean;
  feeder_id: string;
  designation: string;
  description: string;
  has_neutral: boolean;
  voltage_ln_v: string;
  ks: string;
  phase: string;
  distribution_type: DistributionType | "";
  network: "MONO" | "TRI";
  voltage_v: string;
  nominal_power: string;
  power_unit: "W" | "kW";
  quantity: string;
  power_factor: string;
  ku: string;
};

export function EntityDialog({
  open,
  kind,
  mode,
  project,
  initial,
  busy,
  error,
  onSubmit,
  onClose,
}: {
  open: boolean;
  kind: EntityKind;
  mode: EntityMode;
  project: ProjectPayload;
  initial?: BoardSummary | FeederSummary | LoadSummary | null;
  busy: boolean;
  error: string | null;
  onSubmit: (payload: Record<string, unknown>) => void;
  onClose: () => void;
}) {
  const rootBoard = project.boards.find((board) => board.type === "TGBT") ?? project.boards[0];
  const terminalFeeders = project.feeders.filter((feeder) => !feeder.downstream_board_id);
  const [form, setForm] = useState<FormState>(() => makeInitial(kind, project, initial, rootBoard, terminalFeeders));
  useEffect(() => {
    if (open) setForm(makeInitial(kind, project, initial, rootBoard, terminalFeeders));
    // Reset only when the dialog opens or its target changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, kind, initial]);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const parentBoard = project.boards.find((board) => board.id === form.parent_board_id) ?? rootBoard;
  const allowedTypes = parentBoard ? allowedDistributionTypes(parentBoard) : [];
  const selectedFeeder = terminalFeeders.find((feeder) => feeder.id === form.feeder_id);
  const monoFeeder = selectedFeeder?.network === "MONO";
  const loadMonoAllowed = !selectedFeeder
    || selectedFeeder.network === "MONO"
    || selectedFeeder.has_neutral === true;
  const title = `${mode === "create" ? "Ajouter" : "Modifier"} ${
    kind === "board" ? "un tableau" : kind === "feeder" ? "un départ" : "un récepteur"
  }`;

  const selectParentBoard = (boardId: string) => {
    const board = project.boards.find((item) => item.id === boardId);
    const nextType = board ? defaultDistributionType(board) : null;
    setForm((current) => ({
      ...current,
      parent_board_id: boardId,
      reference: mode === "create" ? nextFeederReference(project, boardId) : current.reference,
      reference_auto: mode === "create",
      distribution_type: nextType ?? "",
      phase: nextType === "MONO_N" ? current.phase || "L1" : "",
    }));
  };

  const selectDistribution = (type: DistributionType | "") => {
    setForm((current) => ({
      ...current,
      distribution_type: type,
      phase: type === "MONO_N" ? current.phase || "L1" : "",
    }));
  };

  const selectLoadFeeder = (feederId: string) => {
    const feeder = terminalFeeders.find((item) => item.id === feederId);
    const network = feeder?.network === "MONO" ? "MONO" : "TRI";
    const voltage = feeder?.network === "MONO"
      ? feeder.voltage_v
      : feeder?.voltage_v ?? "400";
    setForm((current) => ({
      ...current,
      feeder_id: feederId,
      network,
      voltage_v: voltage,
      phase: network === "MONO" ? feeder?.phase ?? "L1" : "",
    }));
  };

  const selectLoadNetwork = (network: "MONO" | "TRI") => {
    if (monoFeeder && network !== "MONO") return;
    if (network === "MONO" && !loadMonoAllowed) return;
    const voltage = network === "TRI"
      ? selectedFeeder?.voltage_v ?? "400"
      : selectedFeeder?.voltage_ln_v ?? selectedFeeder?.voltage_v ?? "230";
    setForm((current) => ({
      ...current,
      network,
      voltage_v: voltage,
      phase: network === "MONO" ? current.phase || "L1" : "",
    }));
  };

  const feederInvalid = kind === "feeder"
    && (!form.distribution_type || (form.distribution_type === "MONO_N" && !form.phase));

  const body = () => {
    if (kind === "board") {
      return (
        <div className="form-grid">
          {mode === "create" && (
            <label><span>Tableau parent</span><select value={form.parent_board_id} onChange={(event) => set("parent_board_id", event.target.value)} data-testid="entity-parent-board">{project.boards.map((board) => <option key={board.id} value={board.id}>{board.designation}</option>)}</select></label>
          )}
          <label><span>Désignation *</span><input value={form.designation} onChange={(event) => set("designation", event.target.value)} data-testid="entity-designation" /></label>
          <label><span>U0</span><input value={form.voltage_ln_v} onChange={(event) => set("voltage_ln_v", event.target.value)} data-testid="entity-voltage-ln" /></label>
          <label className="checkbox-label"><input type="checkbox" checked={form.has_neutral} onChange={(event) => set("has_neutral", event.target.checked)} data-testid="entity-neutral" /> Neutre disponible</label>
          <label className="wide-field"><span>Description</span><textarea rows={2} value={form.description} onChange={(event) => set("description", event.target.value)} data-testid="entity-description" /></label>
        </div>
      );
    }
    if (kind === "feeder") {
      return (
        <div className="form-grid">
          {mode === "create" && (
            <label><span>Tableau parent</span><select value={form.parent_board_id} onChange={(event) => selectParentBoard(event.target.value)} data-testid="entity-parent-board">{project.boards.map((board) => <option key={board.id} value={board.id}>{board.designation}</option>)}</select></label>
          )}
          <label><span>Repère du départ</span><input value={form.reference} onChange={(event) => { set("reference", event.target.value); set("reference_auto", false); }} data-testid="entity-reference" /></label>
          <label><span>Désignation du départ *</span><input value={form.designation} onChange={(event) => set("designation", event.target.value)} data-testid="entity-designation" /></label>
          <label><span>Type de départ *</span>
            <select value={form.distribution_type} onChange={(event) => selectDistribution(event.target.value as DistributionType | "")} data-testid="entity-distribution">
              {!allowedTypes.length && <option value="">Aucune distribution compatible</option>}
              {(["MONO_N", "TRI_NO_N", "TRI_N"] as DistributionType[]).map((type) => (
                <option key={type} value={type} disabled={!allowedTypes.includes(type)}>
                  {DISTRIBUTION_LABELS[type]}
                </option>
              ))}
            </select>
          </label>
          {parentBoard && form.distribution_type && (
            <p className="form-note wide-field" data-testid="entity-distribution-summary">
              {distributionSummary(parentBoard, form.distribution_type)}
            </p>
          )}
          {form.distribution_type === "MONO_N" && (
            <label><span>Phase *</span><select value={form.phase} onChange={(event) => set("phase", event.target.value)} data-testid="entity-phase"><option value="">—</option><option value="L1">L1</option><option value="L2">L2</option><option value="L3">L3</option></select></label>
          )}
          {form.distribution_type === "MONO_N" && (
            <p className="form-note wide-field">Ce départ porte une phase unique. Le neutre est requis par construction.</p>
          )}
          {form.distribution_type === "TRI_N" && (
            <p className="form-note wide-field">Le neutre est présent, mais le départ ne porte pas de phase unique. Les récepteurs monophasés pourront être répartis sur L1/L2/L3.</p>
          )}
          <label><span>Ks</span><input value={form.ks} onChange={(event) => set("ks", event.target.value)} placeholder="0,90" data-testid="entity-ks" /></label>
          <label className="wide-field"><span>Description</span><textarea rows={2} value={form.description} onChange={(event) => set("description", event.target.value)} data-testid="entity-description" /></label>
        </div>
      );
    }
    return (
      <div className="form-grid">
        <label><span>Départ</span><select value={form.feeder_id} onChange={(event) => selectLoadFeeder(event.target.value)} data-testid="entity-feeder">{terminalFeeders.map((feeder) => <option key={feeder.id} value={feeder.id}>{feederLabel(feeder)} ({feeder.id})</option>)}</select></label>
        <label><span>Désignation *</span><input value={form.designation} onChange={(event) => set("designation", event.target.value)} data-testid="entity-designation" /></label>
        {monoFeeder ? (
          <label><span>Réseau (hérité)</span><input value="Monophasé" readOnly data-testid="entity-network" /></label>
        ) : (
          <label><span>Réseau</span><select value={form.network} onChange={(event) => selectLoadNetwork(event.target.value as "MONO" | "TRI")} data-testid="entity-network"><option value="MONO" disabled={!loadMonoAllowed}>Monophasé</option><option value="TRI">Triphasé</option></select></label>
        )}
        <label><span>Tension{monoFeeder ? " (héritée)" : ""}</span><input value={form.voltage_v} onChange={(event) => set("voltage_v", event.target.value)} readOnly={monoFeeder} data-testid="entity-voltage" /></label>
        <label><span>Puissance nominale *</span><input value={form.nominal_power} onChange={(event) => set("nominal_power", event.target.value)} data-testid="entity-power" /></label>
        <label><span>Unité</span><select value={form.power_unit} onChange={(event) => set("power_unit", event.target.value as "W" | "kW")} data-testid="entity-power-unit"><option value="W">W</option><option value="kW">kW</option></select></label>
        <label><span>Quantité</span><input value={form.quantity} onChange={(event) => set("quantity", event.target.value)} inputMode="numeric" data-testid="entity-quantity" /></label>
        <label><span>Cos φ</span><input value={form.power_factor} onChange={(event) => set("power_factor", event.target.value)} data-testid="entity-pf" /></label>
        <label><span>Ku</span><input value={form.ku} onChange={(event) => set("ku", event.target.value)} data-testid="entity-ku" /></label>
        {form.network === "MONO" && (
          monoFeeder && mode === "create" ? (
            <label><span>Phase (héritée du départ)</span><input value={form.phase || selectedFeeder?.phase || "L1"} readOnly data-testid="entity-phase" /></label>
          ) : (
            <label><span>Phase</span><select value={form.phase} onChange={(event) => set("phase", event.target.value)} data-testid="entity-phase"><option value="">?</option><option value="L1">L1</option><option value="L2">L2</option><option value="L3">L3</option></select></label>
          )
        )}
        {monoFeeder && mode === "create" && (
          <p className="form-note wide-field">Phase et tension héritées du départ monophas?. La phase ne peut pas ?tre choisie librement à la création.</p>
        )}
        {monoFeeder && mode === "edit" && (
          <p className="form-note wide-field" data-testid="load-phase-sync-note">Modifier cette phase déplacera le départ monophas? et tous ses récepteurs, en une seule opération atomique.</p>
        )}
        {form.network === "TRI" && selectedFeeder?.network === "TRI" && selectedFeeder.has_neutral === false && (
          <p className="form-note wide-field">Ce départ triphasé ne possède pas de neutre : les récepteurs monophasés phase-neutre sont refusés.</p>
        )}
        {form.network === "TRI" && <p className="form-note wide-field">Un r?cepteur triphasé ne porte pas de phase unique.</p>}
      </div>
    );
  };

  return (
    <FormModal
      open={open}
      title={title}
      description={kind === "load" ? "Les résultats seront recalculés par le moteur Python après validation." : "L'opération est validée par les invariants du modèle avant d'être appliquée."}
      onClose={onClose}
      testId="entity-dialog"
      wide
      footer={
        <>
          <button type="button" className="button button-ghost" onClick={onClose} disabled={busy}>Annuler</button>
          <button
            type="button"
            className="button button-primary"
            disabled={busy || !form.designation.trim() || feederInvalid}
            onClick={() => onSubmit(formPayload(kind, mode, form, initial))}
          >
            {busy ? "Application…" : "Valider"}
          </button>
        </>
      }
    >
      {error && <div className="inline-alert inline-alert-error">{error}</div>}
      {body()}
    </FormModal>
  );
}

function makeInitial(
  kind: EntityKind,
  project: ProjectPayload,
  initial: BoardSummary | FeederSummary | LoadSummary | null | undefined,
  rootBoard: BoardSummary | undefined,
  terminalFeeders: FeederSummary[],
): FormState {
  void kind;
  const board = initial && "type" in initial ? initial : undefined;
  const feeder = initial && "member_count" in initial ? initial : undefined;
  const load = initial && "installed_power_w" in initial ? initial : undefined;
  const feederParent = feeder
    ? project.boards.find((item) => item.id === feeder.parent_board_id)
    : rootBoard;
  const parentBoard = board ?? feederParent ?? rootBoard;
  const feederType = feeder ? distributionFromFeeder(feeder) : defaultDistributionType(parentBoard ?? rootBoard ?? project.boards[0]);
  const selectedFeeder = terminalFeeders.find(
    (item) => item.id === (load?.feeder_id ?? terminalFeeders[0]?.id),
  );
  const loadNetwork = load?.network === "MONO" || load?.network === "TRI"
    ? load.network
    : selectedFeeder?.network === "MONO"
      ? "MONO"
      : "TRI";
  const loadVoltage = selectedFeeder?.network === "MONO"
    ? selectedFeeder.voltage_v
    : load?.voltage_v
      ?? (loadNetwork === "TRI" ? selectedFeeder?.voltage_v : selectedFeeder?.voltage_ln_v)
      ?? (loadNetwork === "TRI" ? "400" : "230");
  const loadPhase = load?.phase
    ?? (selectedFeeder?.network === "MONO" ? selectedFeeder.phase ?? "L1" : "");
  const initialParentId = board?.id ?? feeder?.parent_board_id ?? rootBoard?.id ?? project.boards[0]?.id ?? "";
  return {
    parent_board_id: initialParentId,
    reference: feeder?.reference ?? (feeder ? "" : nextFeederReference(project, initialParentId)),
    reference_auto: feeder ? false : true,
    feeder_id: load?.feeder_id ?? selectedFeeder?.id ?? terminalFeeders[0]?.id ?? "",
    designation: board?.designation ?? feeder?.designation ?? load?.designation ?? "",
    description: feeder?.description ?? "",
    has_neutral: board?.has_neutral ?? feeder?.has_neutral ?? true,
    voltage_ln_v: board?.phase_voltage_v ?? feeder?.voltage_ln_v ?? "230",
    ks: feeder?.ks ?? "",
    phase: feeder?.phase ?? loadPhase,
    distribution_type: feederType ?? "",
    network: loadNetwork,
    voltage_v: loadVoltage,
    nominal_power: load?.nominal_power ?? "1000",
    power_unit: (load?.power_unit as "W" | "kW") ?? "W",
    quantity: String(load?.quantity ?? 1),
    power_factor: load?.power_factor ?? "0.9",
    ku: load?.ku ?? "1",
  };
}

function formPayload(
  kind: EntityKind,
  mode: EntityMode,
  form: FormState,
  initial: BoardSummary | FeederSummary | LoadSummary | null | undefined,
): Record<string, unknown> {
  if (kind === "board") {
    const base = {
      designation: form.designation,
      description: form.description,
      has_neutral: form.has_neutral,
      voltage_ln_v: form.voltage_ln_v || null,
    };
    if (mode === "create") return { ...base, parent_board_id: form.parent_board_id };
    return base;
  }
  if (kind === "feeder") {
    const base = {
      reference: form.reference || null,
      auto_reference: mode === "create" ? form.reference_auto : false,
      designation: form.designation,
      description: form.description,
      ks: form.ks || null,
      distribution_type: form.distribution_type || null,
      phase: form.distribution_type === "MONO_N" ? form.phase || null : null,
    };
    if (mode === "create") return { ...base, parent_board_id: form.parent_board_id };
    return base;
  }
  const base = {
    feeder_id: form.feeder_id || null,
    designation: form.designation,
    network: form.network,
    voltage_v: form.voltage_v,
    nominal_power: form.nominal_power,
    power_unit: form.power_unit,
    quantity: Number(form.quantity || 1),
    power_factor: form.power_factor,
    ku: form.ku,
    phase: form.network === "MONO" ? form.phase || null : null,
  };
  void initial;
  return base;
}
