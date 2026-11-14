import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  badge,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  badge?: ReactNode;
}) {
  return (
    <section className="page-header">
      <div className="page-header-copy">
        <span className="eyebrow eyebrow-red">{eyebrow}</span>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      <div className="page-header-side">
        {badge}
        {actions && <div className="page-header-actions">{actions}</div>}
      </div>
    </section>
  );
}
