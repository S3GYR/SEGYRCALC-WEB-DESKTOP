import { useEffect, useMemo, useState } from "react";
import { FormModal } from "./FormModal";
import {
  allowedDistributionTypes,
  defaultDistributionType,
  distributionSummary,
  DISTRIBUTION_LABELS,
  type DistributionType,
} from "../data/distribution";
import { nextFeederReference } from "../data/feederReference";
import { suggestPhase, type PhaseCode } from "../data/phaseSuggestion";
import type { BoardSummary, ProjectPayload } from "../types";

type LoadNetwork = "MONO" | "TRI";
type FieldKey =
  | "feeder_reference"
  | "designation"
  | "distribution_type"
  | "phase"
  | "load_phase"
  | "nominal_power"
  | "quantity"
  | "power_factor"
  | "ku"
  | "ks";

type FormState = {
  feeder_reference: string;
  feeder_reference_auto: boolean;
  designation: string;
  description: string;
  distribution_type: DistributionType | "";
  feeder_phase: string;
  phase_manual: boolean;
  ks: string;
  load_network: LoadNetwork;
  load_phase: string;
  load_voltage: string;
  nominal_power: string;
  power_unit: "W" | "kW";
  quantity: string;
  power_factor: string;
  ku: string;
};

export function FeederLoadDialog({
  open,
  project,
  parentBoardId,
  busy,
  error,
  onSubmit,
  onClose,
}: {
  open: boolean;
  project: ProjectPayload;
  parentBoardId: string;
  busy: boolean;
  error: string | null;
  onSubmit: (payload: Record<string, unknown>) => void;
  onClose: () => void;
}) {
  const parentBoard = project.boards.find((board) => board.id === parentBoardId) ?? project.boards[0];
  const [form, setForm] = useState<FormState>(() => makeInitial(parentBoard, project, parentBoardId));
  const [touched, setTouched] = useState<Partial<Record<FieldKey, boolean>>>({});
  const [attempted, setAttempted] = useState(false);
  useEffect(() => {
    if (open) {
      setForm(makeInitial(parentBoard, project, parentBoardId));
      setTouched({});
      setAttempted(false);
    }
    // Reset only when the dialog opens or the selected board changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, parentBoardId]);

  const allowedTypes = useMemo(
    () => (parentBoard ? allowedDistributionTypes(parentBoard) : []),
    [parentBoard],
  );
  const loadMonoAllowed = form.distribution_type === "MONO_N"
    || (form.distribution_type === "TRI_N" && parentBoard?.has_neutral === true);
  const phaseVoltage = parentBoard?.phase_voltage_v
    ?? (parentBoard?.network === "MONO" ? parentBoard.voltage_v : "230");
  const lineVoltage = parentBoard?.voltage_v ?? "400";
  const suggestion = useMemo(() => suggestPhase(parentBoard), [parentBoard]);
  const phaseApplicable = form.distribution_type === "MONO_N"
    || (form.distribution_type === "TRI_N" && form.load_network === "MONO");
  const fieldErrors = validate(form, allowedTypes);
  const validation = Object.keys(fieldErrors) as FieldKey[];
  const visibleError = (key: FieldKey): string | null => {
    if (!(attempted || touched[key])) return null;
    return fieldErrors[key] ?? null;
  };

  const set = <K extends keyof FormState>(key: K, value: FormState[K], touchedKey?: FieldKey) => {
    setForm((current) => ({ ...current, [key]: value }));
    if (touchedKey) setTouched((current) => ({ ...current, [touchedKey]: true }));
  };

  useEffect(() => {
    if (!phaseApplicable || form.phase_manual || !suggestion.phase) return;
    setForm((current) => {
      if (current.phase_manual) return current;
      if (current.distribution_type === "MONO_N" && current.feeder_phase === suggestion.phase) {
        return current;
      }
      if (current.distribution_type === "TRI_N" && current.load_phase === suggestion.phase) {
        return current;
      }
      return {
        ...current,
        feeder_phase: current.distribution_type === "MONO_N" ? suggestion.phase : current.feeder_phase,
        load_phase: suggestion.phase,
      };
    });
    // A manual selection must never be overwritten by a recomputed suggestion.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phaseApplicable, suggestion.phase, form.phase_manual]);

  const selectDistribution = (type: DistributionType | "") => {
    setForm((current) => {
      const network: LoadNetwork = type === "MONO_N" ? "MONO" : "TRI";
      const suggested = suggestion.phase ?? "L1";
      const retainedPhase = current.phase_manual
        ? current.feeder_phase || current.load_phase || suggested
        : suggested;
      return {
        ...current,
        distribution_type: type,
        feeder_phase: type === "MONO_N" ? retainedPhase : "",
        load_network: network,
        load_phase: type === "MONO_N" ? retainedPhase : "",
        load_voltage: type === "MONO_N" ? phaseVoltage : lineVoltage,
      };
    });
    setTouched((current) => ({ ...current, distribution_type: true }));
  };

  const selectFeederPhase = (phase: string) => {
    setForm((current) => ({
      ...current,
      feeder_phase: phase,
      phase_manual: true,
      load_phase: current.distribution_type === "MONO_N" ? phase : current.load_phase,
    }));
    setTouched((current) => ({ ...current, phase: true }));
  };

  const selectLoadPhase = (phase: PhaseCode) => {
    setForm((current) => ({ ...current, load_phase: phase, phase_manual: true }));
    setTouched((current) => ({ ...current, load_phase: true }));
  };

  const selectLoadNetwork = (network: LoadNetwork) => {
    if (form.distribution_type === "MONO_N" && network !== "MONO") return;
    if (network === "MONO" && !loadMonoAllowed) return;
    setForm((current) => {
      const suggested = suggestion.phase ?? "L1";
      return {
        ...current,
        load_network: network,
        load_phase: network === "MONO"
          ? current.distribution_type === "MONO_N"
            ? current.feeder_phase || suggested
            : current.phase_manual
              ? current.load_phase || suggested
              : suggested
          : "",
        load_voltage: network === "MONO" ? phaseVoltage : lineVoltage,
      };
    });
    setTouched((current) => ({ ...current, load_phase: true }));
  };

  const submit = () => {
    setAttempted(true);
    if (validation.length > 0) return;
    onSubmit(formPayload(form, parentBoard.id));
  };

  if (!parentBoard) return null;

  return (
    <FormModal
      open={open}
      title="Créer un départ électrique"
      description="Le départ et son premier récepteur sont créés ensemble par une seule opération atomique."
      onClose={onClose}
      testId="feeder-load-dialog"
      wide
      footer={
        <>
          <button type="button" className="button button-ghost" onClick={onClose} disabled={busy}>Annuler</button>
          <button
            type="button"
            className="button button-primary"
            disabled={busy || validation.length > 0}
            onClick={submit}
            data-testid="feeder-load-submit"
          >
            {busy ? "Création en cours..." : "Créer le départ"}
          </button>
        </>
      }
    >
      {error && <div className="inline-alert inline-alert-error">{error}</div>}

      <div className="form-grid form-grid-compact" data-testid="feeder-load-unified-form">
        <label>
          <span>Tableau parent</span>
          <input value={`${parentBoard.designation} (${parentBoard.id})`} readOnly data-testid="feeder-load-parent" />
        </label>
        <label>
          <span>Repère du départ *</span>
          <input
            value={form.feeder_reference}
            onChange={(event) => {
              set("feeder_reference", event.target.value, "feeder_reference");
              set("feeder_reference_auto", false);
            }}
            aria-invalid={Boolean(visibleError("feeder_reference"))}
            data-testid="feeder-load-feeder-reference"
          />
          {visibleError("feeder_reference") && <span className="field-error" data-testid="feeder-load-reference-error">{visibleError("feeder_reference")}</span>}
        </label>
        <label>
          <span>Désignation *</span>
          <input
            value={form.designation}
            onChange={(event) => set("designation", event.target.value, "designation")}
            aria-invalid={Boolean(visibleError("designation"))}
            data-testid="feeder-load-designation"
          />
          {visibleError("designation") && <span className="field-error" data-testid="feeder-load-designation-error">{visibleError("designation")}</span>}
        </label>
        <label>
          <span>Distribution électrique *</span>
          <select
            value={form.distribution_type}
            onChange={(event) => selectDistribution(event.target.value as DistributionType | "")}
            aria-invalid={Boolean(visibleError("distribution_type"))}
            data-testid="feeder-load-distribution"
          >
            {!allowedTypes.length && <option value="">Aucune distribution compatible</option>}
            {(["MONO_N", "TRI_NO_N", "TRI_N"] as DistributionType[]).map((type) => (
              <option key={type} value={type} disabled={!allowedTypes.includes(type)}>
                {DISTRIBUTION_LABELS[type]}
              </option>
            ))}
          </select>
          {visibleError("distribution_type") && <span className="field-error">{visibleError("distribution_type")}</span>}
        </label>
        {form.distribution_type === "TRI_N" && (
          <label>
            <span>R?seau du r?cepteur</span>
            <select
              value={form.load_network}
              onChange={(event) => selectLoadNetwork(event.target.value as LoadNetwork)}
              data-testid="feeder-load-network"
            >
              <option value="TRI">Triphas?</option>
              <option value="MONO" disabled={!loadMonoAllowed}>Monophas?</option>
            </select>
          </label>
        )}
        {form.distribution_type === "MONO_N" ? (
          <label>
            <span>Phase du récepteur (et du départ) *</span>
            <select
              value={form.feeder_phase}
              onChange={(event) => selectFeederPhase(event.target.value)}
              aria-invalid={Boolean(visibleError("phase"))}
              data-testid="feeder-load-phase"
            >
              <option value="">—</option>
              <option value="L1">L1</option>
              <option value="L2">L2</option>
              <option value="L3">L3</option>
            </select>
            {visibleError("phase") && <span className="field-error">{visibleError("phase")}</span>}
            <span className="phase-suggestion-note">Phase conseillée automatiquement selon les charges du tableau.</span>
          </label>
        ) : (
          <>
            <label>
              <span>Tension héritée</span>
              <input value={`${lineVoltage} V`} readOnly data-testid="feeder-load-voltage" />
            </label>
            {form.distribution_type === "TRI_N" && form.load_network === "MONO" && (
              <label>
                <span>Phase du récepteur *</span>
                <select
                  value={form.load_phase}
                  onChange={(event) => selectLoadPhase(event.target.value as PhaseCode)}
                  aria-invalid={Boolean(visibleError("load_phase"))}
                  data-testid="feeder-load-load-phase"
                >
                  <option value="">—</option>
                  <option value="L1">L1</option>
                  <option value="L2">L2</option>
                  <option value="L3">L3</option>
                </select>
                {visibleError("load_phase") && <span className="field-error">{visibleError("load_phase")}</span>}
                <span className="phase-suggestion-note">Phase conseillée automatiquement selon les charges du tableau.</span>
              </label>
            )}
          </>
        )}
        {phaseApplicable && (
          <p className="phase-suggestion wide-field" data-testid="feeder-load-phase-suggestion">
            {suggestion.message}
            {suggestion.phase && suggestion.source === "power" ? " Indicateur : puissance active par phase." : ""}
          </p>
        )}
        <label>
          <span>Puissance du récepteur *</span>
          <input
            value={form.nominal_power}
            onChange={(event) => set("nominal_power", event.target.value, "nominal_power")}
            inputMode="decimal"
            aria-invalid={Boolean(visibleError("nominal_power"))}
            data-testid="feeder-load-power"
          />
          {visibleError("nominal_power") && <span className="field-error">{visibleError("nominal_power")}</span>}
        </label>
        <label>
          <span>Unité de puissance</span>
          <select value={form.power_unit} onChange={(event) => set("power_unit", event.target.value as "W" | "kW")} data-testid="feeder-load-power-unit">
            <option value="W">W</option>
            <option value="kW">kW</option>
          </select>
        </label>
        <label>
          <span>Quantité *</span>
          <input
            value={form.quantity}
            onChange={(event) => set("quantity", event.target.value, "quantity")}
            inputMode="numeric"
            aria-invalid={Boolean(visibleError("quantity"))}
            data-testid="feeder-load-quantity"
          />
          {visibleError("quantity") && <span className="field-error">{visibleError("quantity")}</span>}
        </label>
        <label>
          <span>cos φ du récepteur</span>
          <input
            value={form.power_factor}
            onChange={(event) => set("power_factor", event.target.value, "power_factor")}
            aria-invalid={Boolean(visibleError("power_factor"))}
            data-testid="feeder-load-pf"
          />
          {visibleError("power_factor") && <span className="field-error">{visibleError("power_factor")}</span>}
        </label>
        <label>
          <span>Ku du récepteur</span>
          <input
            value={form.ku}
            onChange={(event) => set("ku", event.target.value, "ku")}
            aria-invalid={Boolean(visibleError("ku"))}
            data-testid="feeder-load-ku"
          />
          {visibleError("ku") && <span className="field-error">{visibleError("ku")}</span>}
        </label>
        <label>
          <span>Ks du départ</span>
          <input
            value={form.ks}
            onChange={(event) => set("ks", event.target.value, "ks")}
            aria-invalid={Boolean(visibleError("ks"))}
            data-testid="feeder-load-ks"
          />
          {visibleError("ks") && <span className="field-error">{visibleError("ks")}</span>}
        </label>
        <label>
          <span>Tension du récepteur</span>
          <input value={form.load_voltage} readOnly data-testid="feeder-load-load-voltage" />
        </label>
        <label className="wide-field">
          <span>Description du départ</span>
          <textarea
            rows={2}
            value={form.description}
            onChange={(event) => set("description", event.target.value)}
            data-testid="feeder-load-feeder-description"
          />
        </label>
        {form.distribution_type && parentBoard && (
          <p className="form-note wide-field" data-testid="feeder-load-distribution-summary">
            {distributionSummary(parentBoard, form.distribution_type)} Cette désignation initiale est utilisée pour le départ et le premier récepteur, puis modifiable indépendamment.
          </p>
        )}
      </div>
    </FormModal>
  );
}

function makeInitial(board: BoardSummary | undefined, project: ProjectPayload, parentBoardId: string): FormState {
  const distribution = board ? defaultDistributionType(board) : null;
  const mono = distribution === "MONO_N";
  const suggested = board ? suggestPhase(board).phase ?? "L1" : "L1";
  const phaseVoltage = board?.phase_voltage_v
    ?? (board?.network === "MONO" ? board.voltage_v : "230");
  const lineVoltage = board?.voltage_v ?? "400";
  return {
    feeder_reference: nextFeederReference(project, parentBoardId),
    feeder_reference_auto: true,
    designation: "",
    description: "",
    distribution_type: distribution ?? "",
    feeder_phase: mono ? suggested : "",
    phase_manual: false,
    ks: "0.9",
    load_network: mono ? "MONO" : "TRI",
    load_phase: mono ? suggested : "",
    load_voltage: mono ? phaseVoltage : lineVoltage,
    nominal_power: "1000",
    power_unit: "W",
    quantity: "1",
    power_factor: "0.9",
    ku: "1",
  };
}

function validate(form: FormState, allowedTypes: DistributionType[]): Partial<Record<FieldKey, string>> {
  const errors: Partial<Record<FieldKey, string>> = {};
  if (!form.feeder_reference.trim()) errors.feeder_reference = "Le repère du départ est obligatoire.";
  if (!form.designation.trim()) errors.designation = "La désignation est obligatoire.";
  if (!form.distribution_type || !allowedTypes.includes(form.distribution_type)) {
    errors.distribution_type = "Sélectionnez une distribution compatible avec le tableau parent.";
  }
  if (form.distribution_type === "MONO_N" && !form.feeder_phase) {
    errors.phase = "La phase du départ monophasé est obligatoire.";
  }
  if (form.load_network === "MONO" && !form.load_phase && form.distribution_type !== "MONO_N") {
    errors.load_phase = "La phase du récepteur monophasé est obligatoire.";
  }
  if (!form.nominal_power.trim() || !Number.isFinite(Number(form.nominal_power)) || Number(form.nominal_power) <= 0) {
    errors.nominal_power = "La puissance doit être strictement positive.";
  }
  if (!Number.isInteger(Number(form.quantity)) || Number(form.quantity) < 1) {
    errors.quantity = "La quantité doit être un entier supérieur ou égal à 1.";
  }
  if (form.power_factor.trim() && (!Number.isFinite(Number(form.power_factor)) || Number(form.power_factor) <= 0 || Number(form.power_factor) > 1)) {
    errors.power_factor = "Le cos φ doit être compris entre 0 et 1.";
  }
  if (form.ku.trim() && (!Number.isFinite(Number(form.ku)) || Number(form.ku) <= 0 || Number(form.ku) > 1)) {
    errors.ku = "Le coefficient Ku doit être compris entre 0 et 1.";
  }
  if (form.ks.trim() && (!Number.isFinite(Number(form.ks)) || Number(form.ks) <= 0 || Number(form.ks) > 1)) {
    errors.ks = "Le coefficient Ks doit être compris entre 0 et 1.";
  }
  return errors;
}

function formPayload(form: FormState, parentBoardId: string): Record<string, unknown> {
  return {
    parent_board_id: parentBoardId,
    feeder: {
      reference: form.feeder_reference,
      auto_reference: form.feeder_reference_auto,
      designation: form.designation,
      description: form.description,
      distribution_type: form.distribution_type || null,
      phase: form.distribution_type === "MONO_N" ? form.feeder_phase || null : null,
      ks: form.ks || null,
    },
    load: {
      designation: form.designation,
      network: form.load_network,
      voltage_v: form.load_voltage,
      nominal_power: form.nominal_power,
      power_unit: form.power_unit,
      quantity: Number(form.quantity || 1),
      power_factor: form.power_factor,
      ku: form.ku,
      phase: form.load_network === "MONO" ? form.load_phase || null : null,
    },
  };
}
