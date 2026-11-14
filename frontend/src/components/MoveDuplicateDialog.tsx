import { useEffect, useMemo, useState } from "react";
import { FormModal } from "./FormModal";
import type { BoardSummary, FeederSummary, LoadSummary, ProjectPayload } from "../types";

type Kind = "board" | "feeder" | "load";
type Action = "move" | "duplicate";

export function MoveDuplicateDialog({
  open,
  action,
  kind,
  project,
  initial,
  busy,
  error,
  onSubmit,
  onClose,
}: {
  open: boolean;
  action: Action;
  kind: Kind;
  project: ProjectPayload;
  initial: BoardSummary | FeederSummary | LoadSummary | null;
  busy: boolean;
  error: string | null;
  onSubmit: (payload: Record<string, unknown>) => void;
  onClose: () => void;
}) {
  const rootBoard = project.boards.find((board) => board.type === "TGBT") ?? project.boards[0];
  const terminalFeeders = useMemo(
    () => project.feeders.filter((feeder) => !feeder.downstream_board_id),
    [project.feeders],
  );
  const parentBoardId = useMemo(() => {
    if (initial && "parent_feeder_id" in initial) {
      const feeder = project.feeders.find((item) => item.id === initial.parent_feeder_id);
      return feeder?.parent_board_id ?? rootBoard?.id ?? "";
    }
    if (initial && "parent_board_id" in initial) return initial.parent_board_id;
    return rootBoard?.id ?? "";
  }, [initial, project.feeders, rootBoard?.id]);
  const [destination, setDestination] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    if (kind === "load") {
      const currentFeeder = initial && "feeder_id" in initial ? initial.feeder_id : terminalFeeders[0]?.id ?? "";
      setDestination(currentFeeder || terminalFeeders[0]?.id || "");
    } else {
      setDestination(parentBoardId || rootBoard?.id || "");
    }
    setFormError(null);
  }, [open, kind, initial, parentBoardId, rootBoard?.id, terminalFeeders]);

  const boardOptions = project.boards.filter((board) => !(kind === "board" && initial && board.id === initial.id));
  const options = kind === "load"
    ? terminalFeeders.map((feeder) => ({
        id: feeder.id,
        label: `${feeder.designation} · ${feeder.id} · ${feeder.parent_board_id}`,
      }))
    : boardOptions.map((board) => ({
        id: board.id,
        label: `${board.designation} · ${board.id} · ${board.type}`,
      }));

  return (
    <FormModal
      open={open}
      title={`${action === "move" ? "Déplacer" : "Dupliquer"} ${
        kind === "board" ? "un tableau" : kind === "feeder" ? "un départ" : "un récepteur"
      }`}
      description={
        action === "move"
          ? "La destination est validée par le backend. Les cycles, doubles parents et incompatibilités sont refusés."
          : kind === "load"
            ? "Le récepteur est copié avec un nouvel identifiant dans le départ choisi."
            : "La copie reçoit de nouveaux identifiants et reconstruit ses relations internes."
      }
      onClose={onClose}
      testId="move-duplicate-dialog"
      footer={
        <>
          <button type="button" className="button button-ghost" onClick={onClose} disabled={busy}>Annuler</button>
          <button
            type="button"
            className="button button-primary"
            disabled={busy || !destination}
            onClick={() => {
              if (!destination) {
                setFormError("Choisissez une destination.");
                return;
              }
              onSubmit(kind === "load" ? { destination_feeder_id: destination } : { destination_board_id: destination });
            }}
          >
            {busy ? "Traitement…" : action === "move" ? "Déplacer" : "Dupliquer"}
          </button>
        </>
      }
    >
      {(error || formError) && <div className="inline-alert inline-alert-error">{error || formError}</div>}
      <label className="path-field">
        <span>{kind === "load" ? "Départ destination" : "Tableau destination"}</span>
        <select value={destination} onChange={(event) => setDestination(event.target.value)} data-testid="destination-select">
          {options.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
        </select>
      </label>
      <p className="form-note">Utilisez « Déplacer vers » plutôt qu'un glisser-déposer : les mêmes invariants métier sont appliqués côté backend.</p>
    </FormModal>
  );
}
