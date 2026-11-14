import { Icon, type IconName } from "../icons";

export function EmptyState({
  title,
  description,
  icon = "info",
  action,
}: {
  title: string;
  description: string;
  icon?: IconName;
  action?: React.ReactNode;
}) {
  return (
    <div className="state-panel" data-testid="empty-state">
      <span className="state-icon"><Icon name={icon} size={26} /></span>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
