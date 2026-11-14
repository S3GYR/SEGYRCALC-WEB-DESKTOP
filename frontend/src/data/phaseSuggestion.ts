import type { BoardSummary, PhaseTriplet } from "../types";

export type PhaseCode = "L1" | "L2" | "L3";

export type PhaseSuggestion =
  | {
      phase: PhaseCode;
      source: "current" | "power";
      message: string;
    }
  | {
      phase: null;
      source: null;
      message: "Suggestion de phase indisponible : données de charge insuffisantes.";
    };

const PHASES: PhaseCode[] = ["L1", "L2", "L3"];
const UNAVAILABLE: PhaseSuggestion = {
  phase: null,
  source: null,
  message: "Suggestion de phase indisponible : données de charge insuffisantes.",
};

function numbers(triplet: PhaseTriplet): number[] | null {
  const values = [triplet.l1, triplet.l2, triplet.l3].map((value) => {
    if (value === null || value === undefined || String(value).trim() === "") return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  });
  return values.some((value) => value === null) ? null : (values as number[]);
}

function choose(
  values: number[],
  source: "current" | "power",
  allowed: PhaseCode[],
): PhaseSuggestion {
  const candidates = PHASES.map((phase, index) => ({ phase, value: values[index] }))
    .filter((candidate) => allowed.includes(candidate.phase));
  if (candidates.length === 0) return UNAVAILABLE;
  const minimum = Math.min(...candidates.map((candidate) => candidate.value));
  const selected = candidates.find((candidate) => candidate.value === minimum) ?? candidates[0];
  return {
    phase: selected.phase,
    source,
    message: `Phase conseillée : ${selected.phase} — phase actuellement la moins chargée.`,
  };
}

export function suggestPhase(
  board: Pick<BoardSummary, "network" | "current_phases" | "p_phases"> | null | undefined,
): PhaseSuggestion {
  if (!board) return UNAVAILABLE;
  if (board.network === "MONO") {
    return choose([0, 0, 0], "current", ["L1"]);
  }
  const allowed: PhaseCode[] = ["L1", "L2", "L3"];
  const currents = numbers(board.current_phases);
  if (currents && currents.some((value) => value > 0)) {
    return choose(currents, "current", allowed);
  }
  const powers = numbers(board.p_phases);
  if (powers && powers.some((value) => value > 0)) {
    return choose(powers, "power", allowed);
  }
  if (currents) return choose(currents, "current", allowed);
  if (powers) return choose(powers, "power", allowed);
  return UNAVAILABLE;
}
