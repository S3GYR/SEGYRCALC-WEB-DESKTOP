import { useEffect, useState } from "react";
import type { SourcePayload, SourceType } from "../types";
import { FormModal } from "./FormModal";

const SOURCE_LABELS: Record<SourceType, string> = {
  AC_THREE_PHASE: "Source AC triphasée",
  AC_SINGLE_PHASE: "Source AC monophasée",
  DC: "Source DC",
  ENEDIS: "Souscription Enedis",
  TRANSFORMER: "Transformateur HTA/BT",
  GENERATOR: "Groupe électrogène",
  BATTERY: "Batterie",
};

const PHASE_OPTIONS = [
  { value: "TRI", label: "Triphasé" },
  { value: "MONO", label: "Monophasé" },
  { value: "DC", label: "DC" },
] as const;

const MODE_OPTIONS = [
  { value: "SINGLE", label: "Source unique" },
  { value: "PARALLEL", label: "Fonctionnement parallèle" },
  { value: "BACKUP", label: "Secours" },
  { value: "ALTERNATE", label: "Alterné" },
] as const;

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return "00000000-0000-4000-8000-000000000001";
}

function defaultPhase(type: SourceType): SourcePayload["phase_system"] {
  if (type === "AC_THREE_PHASE" || type === "TRANSFORMER" || type === "GENERATOR") return "TRI";
  if (type === "AC_SINGLE_PHASE") return "MONO";
  if (type === "DC" || type === "BATTERY") return "DC";
  return "TRI";
}

function emptySource(type: SourceType = "AC_THREE_PHASE"): SourcePayload {
  return {
    id: newId(),
    source_type: type,
    reference: "",
    designation: "",
    quantity: 1,
    phase_system: defaultPhase(type),
    rated_power: null,
    rated_power_unit: "KVA",
    nominal_voltage: null,
    voltage_unit: "V",
    frequency_hz: null,
    power_factor: null,
    primary_voltage: null,
    primary_voltage_unit: "V",
    secondary_voltage: null,
    secondary_voltage_unit: "V",
    short_circuit_voltage_percent: null,
    coupling: "",
    operating_mode: "SINGLE",
    active_power: null,
    active_power_unit: "W",
    capacity_ah: null,
    max_current_a: null,
    max_power_w: null,
    technology: "",
    connection_type: "",
    subscribed_power_kva: null,
    connection_power_kva: null,
  };
}

function typeDefaults(type: SourceType): SourcePayload {
  return emptySource(type);
}

function visibleFields(type: SourceType): Set<string> {
  switch (type) {
    case "AC_THREE_PHASE":
    case "AC_SINGLE_PHASE":
      return new Set(["power", "voltage", "frequency", "power_factor", "phase"]);
    case "DC":
      return new Set(["active_power", "voltage"]);
    case "TRANSFORMER":
      return new Set(["power", "primary_voltage", "secondary_voltage", "frequency", "uk", "coupling"]);
    case "GENERATOR":
      return new Set(["power", "voltage", "frequency", "power_factor", "operating_mode", "phase"]);
    case "BATTERY":
      return new Set(["voltage", "capacity", "max_current", "max_power", "technology"]);
    case "ENEDIS":
      return new Set(["voltage", "connection_type", "subscribed_power", "connection_power", "phase"]);
  }
}

function valueOrNull(value: string): string | null {
  return value.trim() === "" ? null : value;
}

export function SourceDialog({
  open,
  initial,
  busy,
  error,
  onSubmit,
  onClose,
}: {
  open: boolean;
  initial: SourcePayload | null;
  busy: boolean;
  error: string | null;
  onSubmit: (source: SourcePayload) => void;
  onClose: () => void;
}) {
  const [form, setForm] = useState<SourcePayload>(() => initial ?? emptySource());

  useEffect(() => {
    if (open) setForm(initial ?? emptySource());
  }, [open, initial]);

  const set = <K extends keyof SourcePayload>(key: K, value: SourcePayload[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const changeType = (type: SourceType) => {
    setForm((current) => ({
      ...typeDefaults(type),
      id: current.id,
      reference: current.reference,
      designation: current.designation,
      quantity: current.quantity,
    }));
  };

  const fields = visibleFields(form.source_type);

  return (
    <FormModal
      open={open}
      title={initial ? "Modifier la source électrique" : "Configurer la source électrique"}
      description="Source unique du projet, issue du modèle V1.5. Aucune association source/TGBT n'est créée."
      onClose={onClose}
      testId="source-dialog"
      wide
      footer={
        <>
          <button type="button" className="button button-ghost" onClick={onClose} disabled={busy}>
            Annuler
          </button>
          <button
            type="button"
            className="button button-primary"
            disabled={busy || !form.reference.trim() || !form.designation.trim()}
            onClick={() => onSubmit({ ...form, quantity: Number(form.quantity) || 1 })}
            data-testid="source-save"
          >
            {busy ? "Enregistrement…" : "Enregistrer la source"}
          </button>
        </>
      }
    >
      {error && <div className="inline-alert inline-alert-error">{error}</div>}
      <div className="form-grid">
        <label>
          <span>Type de source *</span>
          <select
            value={form.source_type}
            onChange={(event) => changeType(event.target.value as SourceType)}
            data-testid="source-type"
          >
            {(Object.keys(SOURCE_LABELS) as SourceType[]).map((type) => (
              <option key={type} value={type}>{SOURCE_LABELS[type]}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Repère *</span>
          <input value={form.reference} onChange={(event) => set("reference", event.target.value)} data-testid="source-reference" />
        </label>
        <label>
          <span>Désignation *</span>
          <input value={form.designation} onChange={(event) => set("designation", event.target.value)} data-testid="source-designation" />
        </label>
        <label>
          <span>Nombre *</span>
          <input
            type="number"
            min={1}
            value={form.quantity}
            onChange={(event) => set("quantity", Number(event.target.value) || 1)}
            data-testid="source-quantity"
          />
        </label>

        {fields.has("power") && (
          <label>
            <span>Puissance nominale</span>
            <span className="numeric-control">
              <input value={form.rated_power ?? ""} onChange={(event) => set("rated_power", valueOrNull(event.target.value))} data-testid="source-power" />
              <select value={form.rated_power_unit} onChange={(event) => set("rated_power_unit", event.target.value as SourcePayload["rated_power_unit"])} data-testid="source-power-unit">
                <option value="KVA">kVA</option>
                <option value="VA">VA</option>
              </select>
            </span>
          </label>
        )}
        {fields.has("active_power") && (
          <label>
            <span>Puissance active</span>
            <span className="numeric-control">
              <input value={form.active_power ?? ""} onChange={(event) => set("active_power", valueOrNull(event.target.value))} data-testid="source-active-power" />
              <select value={form.active_power_unit} onChange={(event) => set("active_power_unit", event.target.value as SourcePayload["active_power_unit"])} data-testid="source-active-power-unit">
                <option value="W">W</option>
                <option value="KW">kW</option>
              </select>
            </span>
          </label>
        )}
        {fields.has("voltage") && (
          <label>
            <span>Tension nominale</span>
            <span className="numeric-control">
              <input value={form.nominal_voltage ?? ""} onChange={(event) => set("nominal_voltage", valueOrNull(event.target.value))} data-testid="source-voltage" />
              <select value={form.voltage_unit} onChange={(event) => set("voltage_unit", event.target.value as SourcePayload["voltage_unit"])} data-testid="source-voltage-unit">
                <option value="V">V</option>
                <option value="KV">kV</option>
              </select>
            </span>
          </label>
        )}
        {fields.has("frequency") && (
          <label>
            <span>Fréquence (Hz)</span>
            <input value={form.frequency_hz ?? ""} onChange={(event) => set("frequency_hz", valueOrNull(event.target.value))} data-testid="source-frequency" />
          </label>
        )}
        {fields.has("power_factor") && (
          <label>
            <span>Facteur de puissance</span>
            <input value={form.power_factor ?? ""} onChange={(event) => set("power_factor", valueOrNull(event.target.value))} data-testid="source-power-factor" />
          </label>
        )}
        {fields.has("primary_voltage") && (
          <label>
            <span>Tension primaire HTA</span>
            <span className="numeric-control">
              <input value={form.primary_voltage ?? ""} onChange={(event) => set("primary_voltage", valueOrNull(event.target.value))} data-testid="source-primary-voltage" />
              <select value={form.primary_voltage_unit} onChange={(event) => set("primary_voltage_unit", event.target.value as SourcePayload["primary_voltage_unit"])}>
                <option value="V">V</option>
                <option value="KV">kV</option>
              </select>
            </span>
          </label>
        )}
        {fields.has("secondary_voltage") && (
          <label>
            <span>Tension secondaire BT</span>
            <span className="numeric-control">
              <input value={form.secondary_voltage ?? ""} onChange={(event) => set("secondary_voltage", valueOrNull(event.target.value))} data-testid="source-secondary-voltage" />
              <select value={form.secondary_voltage_unit} onChange={(event) => set("secondary_voltage_unit", event.target.value as SourcePayload["secondary_voltage_unit"])}>
                <option value="V">V</option>
                <option value="KV">kV</option>
              </select>
            </span>
          </label>
        )}
        {fields.has("uk") && (
          <label>
            <span>Uk (%)</span>
            <input value={form.short_circuit_voltage_percent ?? ""} onChange={(event) => set("short_circuit_voltage_percent", valueOrNull(event.target.value))} data-testid="source-uk" />
          </label>
        )}
        {fields.has("coupling") && (
          <label>
            <span>Couplage</span>
            <input value={form.coupling} onChange={(event) => set("coupling", event.target.value)} data-testid="source-coupling" />
          </label>
        )}
        {fields.has("operating_mode") && (
          <label>
            <span>Mode de fonctionnement</span>
            <select value={form.operating_mode} onChange={(event) => set("operating_mode", event.target.value as SourcePayload["operating_mode"])} data-testid="source-operating-mode">
              {MODE_OPTIONS.map((mode) => <option key={mode.value} value={mode.value}>{mode.label}</option>)}
            </select>
          </label>
        )}
        {fields.has("phase") && (
          <label>
            <span>Nature du raccordement</span>
            <select value={form.phase_system ?? "TRI"} onChange={(event) => set("phase_system", event.target.value as SourcePayload["phase_system"])} data-testid="source-phase">
              {PHASE_OPTIONS.map((phase) => <option key={phase.value} value={phase.value}>{phase.label}</option>)}
            </select>
          </label>
        )}
        {fields.has("capacity") && (
          <label>
            <span>Capacité (Ah)</span>
            <input value={form.capacity_ah ?? ""} onChange={(event) => set("capacity_ah", valueOrNull(event.target.value))} data-testid="source-capacity" />
          </label>
        )}
        {fields.has("max_current") && (
          <label>
            <span>Courant max (A)</span>
            <input value={form.max_current_a ?? ""} onChange={(event) => set("max_current_a", valueOrNull(event.target.value))} data-testid="source-max-current" />
          </label>
        )}
        {fields.has("max_power") && (
          <label>
            <span>Puissance max (W)</span>
            <input value={form.max_power_w ?? ""} onChange={(event) => set("max_power_w", valueOrNull(event.target.value))} data-testid="source-max-power" />
          </label>
        )}
        {fields.has("technology") && (
          <label>
            <span>Technologie</span>
            <input value={form.technology} onChange={(event) => set("technology", event.target.value)} data-testid="source-technology" />
          </label>
        )}
        {fields.has("connection_type") && (
          <label>
            <span>Type de raccordement</span>
            <input value={form.connection_type} onChange={(event) => set("connection_type", event.target.value)} data-testid="source-connection-type" />
          </label>
        )}
        {fields.has("subscribed_power") && (
          <label>
            <span>Puissance souscrite (kVA)</span>
            <input value={form.subscribed_power_kva ?? ""} onChange={(event) => set("subscribed_power_kva", valueOrNull(event.target.value))} data-testid="source-subscribed-power" />
          </label>
        )}
        {fields.has("connection_power") && (
          <label>
            <span>Puissance de raccordement (kVA)</span>
            <input value={form.connection_power_kva ?? ""} onChange={(event) => set("connection_power_kva", valueOrNull(event.target.value))} data-testid="source-connection-power" />
          </label>
        )}
      </div>
    </FormModal>
  );
}
