export type TabItem<T extends string> = {
  id: T;
  label: string;
  count?: number;
  testId?: string;
};

export function Tabs<T extends string>({
  items,
  active,
  onChange,
  label,
}: {
  items: Array<TabItem<T>>;
  active: T;
  onChange: (id: T) => void;
  label: string;
}) {
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          role="tab"
          aria-selected={active === item.id}
          className={`tab ${active === item.id ? "is-active" : ""}`}
          onClick={() => onChange(item.id)}
          data-testid={item.testId}
        >
          {item.label}
          {item.count !== undefined && <span className="tab-count">{item.count}</span>}
        </button>
      ))}
    </div>
  );
}
