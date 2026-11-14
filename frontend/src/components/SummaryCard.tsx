import { Icon, type IconName } from "../icons";

export function SummaryCard({
  label,
  value,
  detail,
  icon,
  tone = "navy",
  testId,
}: {
  label: string;
  value: string;
  detail: string;
  icon: IconName;
  tone?: "navy" | "red" | "ok" | "warn" | "neutral";
  testId?: string;
}) {
  return (
    <div className={`summary-card summary-${tone}`} data-testid={testId}>
      <div className="summary-card-top">
        <span>{label}</span>
        <span className="summary-card-icon"><Icon name={icon} size={18} /></span>
      </div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}
