const formatterCache = new Map<string, Intl.NumberFormat>();

function numberFormatter(decimals: number): Intl.NumberFormat {
  const key = String(decimals);
  const existing = formatterCache.get(key);
  if (existing) return existing;
  const formatter = new Intl.NumberFormat("fr-FR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  formatterCache.set(key, formatter);
  return formatter;
}

export function formatNumber(value: string | null | undefined, decimals = 2): string {
  if (value === null || value === undefined || value === "") return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return numberFormatter(decimals).format(numeric);
}

export function formatPower(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  if (Math.abs(numeric) >= 1000) return `${formatNumber(String(numeric / 1000), 2)} kW`;
  return `${formatNumber(String(numeric), 2)} W`;
}

export function formatApparentPower(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return `${formatNumber(String(numeric / 1000), 2)} kVA`;
}

export function formatReactivePower(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  if (Math.abs(numeric) >= 1000) return `${formatNumber(String(numeric / 1000), 2)} kvar`;
  return `${formatNumber(String(numeric), 2)} var`;
}

export function formatPowerIn(value: string | null | undefined, unit: "W" | "kW"): string {
  if (value === null || value === undefined) return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return unit === "kW"
    ? `${formatNumber(String(numeric / 1000), 2)} kW`
    : `${formatNumber(String(numeric), 1)} W`;
}

export function formatReactiveIn(value: string | null | undefined, unit: "var" | "kvar"): string {
  if (value === null || value === undefined) return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return unit === "kvar"
    ? `${formatNumber(String(numeric / 1000), 2)} kvar`
    : `${formatNumber(String(numeric), 1)} var`;
}

export function formatApparentIn(value: string | null | undefined, unit: "VA" | "kVA"): string {
  if (value === null || value === undefined) return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return unit === "kVA"
    ? `${formatNumber(String(numeric / 1000), 2)} kVA`
    : `${formatNumber(String(numeric), 1)} VA`;
}

/** Exact decimal subtraction for presentation deltas (no electrical formula). */
export function decimalDelta(after: string | null | undefined, before: string | null | undefined): string | null {
  if (!after || !before) return null;
  const parse = (value: string): { negative: boolean; digits: bigint; scale: number } | null => {
    const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(value.trim());
    if (!match) return null;
    const fraction = match[3] ?? "";
    return {
      negative: match[1] === "-",
      digits: BigInt(match[2] + fraction),
      scale: fraction.length,
    };
  };
  const left = parse(after);
  const right = parse(before);
  if (!left || !right) return null;
  const scale = Math.max(left.scale, right.scale);
  const leftDigits = left.digits * 10n ** BigInt(scale - left.scale);
  const rightDigits = right.digits * 10n ** BigInt(scale - right.scale);
  const leftSigned = left.negative ? -leftDigits : leftDigits;
  const rightSigned = right.negative ? -rightDigits : rightDigits;
  const delta = leftSigned - rightSigned;
  const negative = delta < 0n;
  const absolute = negative ? -delta : delta;
  const text = absolute.toString().padStart(scale + 1, "0");
  const integer = text.slice(0, text.length - scale);
  const fraction = scale > 0 ? text.slice(text.length - scale).replace(/0+$/, "") : "";
  return `${negative ? "-" : ""}${integer}${fraction ? `.${fraction}` : ""}`;
}

export function formatCurrent(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return `${formatNumber(String(numeric), 2)} A`;
}

export function formatPercent(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return `${formatNumber(String(numeric), 2)} %`;
}

export function formatUnit(value: string | null | undefined): string {
  return value ?? "—";
}

export function statusLabel(status: string): string {
  switch (status) {
    case "OK":
      return "Conforme";
    case "AVERTISSEMENT":
      return "Avertissement";
    case "ERREUR":
      return "Erreur";
    case "NON_CALCULABLE":
      return "Non calculable";
    case "SYNTHETIC":
      return "Synthétique";
    default:
      return status || "Inconnu";
  }
}

export function statusTone(status: string): "ok" | "warn" | "error" | "neutral" | "synthetic" {
  if (status === "OK") return "ok";
  if (status === "AVERTISSEMENT") return "warn";
  if (status === "ERREUR" || status === "NON_CALCULABLE") return "error";
  if (status === "SYNTHETIC") return "synthetic";
  return "neutral";
}

export function phaseValue(value: string | null | undefined): string {
  return formatCurrent(value);
}

export function shortDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function shortHash(value: string, size = 16): string {
  return value.length <= size ? value : `${value.slice(0, size)}…`;
}

export function compareText(left: string, right: string): number {
  return left.localeCompare(right, "fr", { sensitivity: "base", numeric: true });
}

export function compareNumeric(
  left: string | null | undefined,
  right: string | null | undefined,
): number {
  const a = left === null || left === undefined || left === "" ? Number.NaN : Number(left);
  const b = right === null || right === undefined || right === "" ? Number.NaN : Number(right);
  if (Number.isNaN(a) && Number.isNaN(b)) return 0;
  if (Number.isNaN(a)) return 1;
  if (Number.isNaN(b)) return -1;
  return a - b;
}
