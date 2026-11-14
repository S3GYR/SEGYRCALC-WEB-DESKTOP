import { statusLabel, statusTone } from "../format";

export function StatusIndicator({
  status,
  compact = false,
  testId,
}: {
  status: string;
  compact?: boolean;
  testId?: string;
}) {
  return (
    <span
      className={`status-indicator status-${statusTone(status)} ${compact ? "status-compact" : ""}`}
      data-testid={testId}
      title={statusLabel(status)}
    >
      <span className="status-dot" />
      {statusLabel(status)}
    </span>
  );
}
