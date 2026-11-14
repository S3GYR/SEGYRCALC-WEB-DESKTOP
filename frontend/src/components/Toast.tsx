import { useEffect } from "react";
import { Icon } from "../icons";

export function Toast({
  message,
  tone = "info",
  onClose,
}: {
  message: string;
  tone?: "info" | "success" | "warning" | "error";
  onClose: () => void;
}) {
  useEffect(() => {
    const timer = window.setTimeout(onClose, 4200);
    return () => window.clearTimeout(timer);
  }, [onClose, message]);

  return (
    <div className={`toast toast-${tone}`} role="status" data-testid="toast">
      <Icon name={tone === "error" ? "alert" : tone === "success" ? "check" : "info"} size={16} />
      <span>{message}</span>
      <button type="button" onClick={onClose} aria-label="Fermer la notification">
        <Icon name="close" size={13} />
      </button>
    </div>
  );
}
