import { Icon } from "../icons";

export function SearchInput({
  value,
  onChange,
  placeholder,
  label,
  testId,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label: string;
  testId?: string;
}) {
  return (
    <label className="search-input">
      <span className="sr-only">{label}</span>
      <Icon name="search" size={15} />
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        data-testid={testId}
        aria-label={label}
        spellCheck={false}
      />
      {value && (
        <button
          type="button"
          className="search-clear"
          onClick={() => onChange("")}
          aria-label="Effacer la recherche"
        >
          <Icon name="close" size={13} />
        </button>
      )}
    </label>
  );
}
