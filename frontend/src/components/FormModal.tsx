import type { ReactNode } from "react";
import { Icon } from "../icons";

export function FormModal({
  open,
  title,
  description,
  children,
  footer,
  onClose,
  testId,
  wide = false,
}: {
  open: boolean;
  title: string;
  description?: string;
  children: ReactNode;
  footer: ReactNode;
  onClose: () => void;
  testId?: string;
  wide?: boolean;
}) {
  if (!open) return null;
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className={`form-modal ${wide ? "form-modal-wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="form-modal-title"
        data-testid={testId}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="form-modal-head">
          <div>
            <h2 id="form-modal-title">{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Fermer">
            <Icon name="close" size={15} />
          </button>
        </div>
        <div className="form-modal-body">{children}</div>
        <div className="form-modal-foot">{footer}</div>
      </div>
    </div>
  );
}
