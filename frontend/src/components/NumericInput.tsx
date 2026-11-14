export function NumericInput({
  value,
  onChange,
  unit,
  label,
  placeholder,
  testId,
}: {
  value: string;
  onChange: (value: string) => void;
  unit: string;
  label: string;
  placeholder?: string;
  testId?: string;
}) {
  return (
    <label className="numeric-input">
      <span>{label}</span>
      <span className="numeric-control">
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          inputMode="decimal"
          data-testid={testId}
          aria-label={label}
        />
        <span className="numeric-unit">{unit}</span>
      </span>
    </label>
  );
}
