import { Icon } from "../icons";

export function Breadcrumb({ items }: { items: string[] }) {
  return (
    <div className="breadcrumb" aria-label="Fil d’Ariane">
      {items.map((item, index) => (
        <span key={`${item}-${index}`}>
          {index > 0 && <Icon name="chevron" size={13} />}
          {index === items.length - 1 ? <strong>{item}</strong> : <span>{item}</span>}
        </span>
      ))}
    </div>
  );
}
