import type { BoardSummary, FeederSummary } from "../types";

export type DistributionType = "MONO_N" | "TRI_NO_N" | "TRI_N";

export const DISTRIBUTION_LABELS: Record<DistributionType, string> = {
  MONO_N: "Monophasé + N — 230 V",
  TRI_NO_N: "Triphasé sans N — 400 V",
  TRI_N: "Triphasé + N — 400/230 V",
};

export function distributionFromFeeder(feeder: Pick<FeederSummary, "network" | "has_neutral">): DistributionType {
  if (feeder.network === "MONO") return "MONO_N";
  return feeder.has_neutral ? "TRI_N" : "TRI_NO_N";
}

export function allowedDistributionTypes(
  board: Pick<BoardSummary, "network" | "has_neutral" | "phase_voltage_v">,
): DistributionType[] {
  if (board.network === "MONO") {
    return board.has_neutral ? ["MONO_N"] : [];
  }
  if (board.network === "TRI") {
    const result: DistributionType[] = ["TRI_NO_N"];
    if (board.has_neutral && board.phase_voltage_v) {
      result.push("MONO_N", "TRI_N");
    }
    return result;
  }
  return [];
}

export function defaultDistributionType(
  board: Pick<BoardSummary, "network" | "has_neutral" | "phase_voltage_v">,
): DistributionType | null {
  const allowed = allowedDistributionTypes(board);
  if (allowed.includes("TRI_N")) return "TRI_N";
  return allowed[0] ?? null;
}

export function distributionSummary(board: BoardSummary, type: DistributionType): string {
  if (type === "MONO_N") {
    const voltage = board.phase_voltage_v
      ?? (board.network === "MONO" ? board.voltage_v : "230");
    return `MONO · ${voltage} V · neutre requis`;
  }
  if (type === "TRI_NO_N") {
    return `TRI · ${board.voltage_v} V · sans neutre`;
  }
  return `TRI · ${board.voltage_v} V / ${board.phase_voltage_v ?? "U0 absent"} V · neutre`;
}
