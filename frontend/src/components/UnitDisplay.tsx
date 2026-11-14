export function UnitDisplay({
  value,
  unit,
  unavailable = false,
}: {
  value: string | null | undefined;
  unit: string;
  unavailable?: boolean;
}) {
  if (unavailable || value === null || value === undefined) {
    return (
      <span className="unit-display is-unavailable" title="Valeur indisponible pour ce récepteur.">
        Non exposé
      </span>
    );
  }
  return (
    <span className="unit-display">
      <strong>{value}</strong>
      <small>{unit}</small>
    </span>
  );
}
