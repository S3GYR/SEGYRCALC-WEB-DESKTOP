import type { FeederSummary, ProjectPayload } from "../types";

const REFERENCE_PATTERN = /^Q([1-9][0-9]*)$/;

export function nextFeederReference(
  project: ProjectPayload,
  parentBoardId: string,
  excludeFeederId?: string,
): string {
  let highest = 0;
  const used = new Set<string>();
  for (const feeder of project.feeders) {
    if (feeder.parent_board_id !== parentBoardId || feeder.id === excludeFeederId) continue;
    const storedReference = (feeder.reference ?? "").trim();
    const reference = storedReference || (REFERENCE_PATTERN.test(feeder.designation.trim()) ? feeder.designation.trim() : "");
    if (!reference) continue;
    used.add(reference);
    const match = REFERENCE_PATTERN.exec(reference);
    if (match) highest = Math.max(highest, Number(match[1]));
  }
  let number = highest + 1;
  while (used.has(`Q${number}`)) number += 1;
  return `Q${number}`;
}

export function feederLabel(feeder: Pick<FeederSummary, "reference" | "designation" | "id">): string {
  const reference = (feeder.reference ?? "").trim();
  const designation = feeder.designation.trim();
  if (reference && designation) return `${reference} — ${designation}`;
  if (reference) return reference;
  if (designation) return designation;
  return feeder.id;
}
