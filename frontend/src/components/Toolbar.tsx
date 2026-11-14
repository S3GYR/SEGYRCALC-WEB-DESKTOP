import type { ReactNode } from "react";

export function Toolbar({ left, right }: { left: ReactNode; right?: ReactNode }) {
  return (
    <div className="toolbar">
      <div className="toolbar-left">{left}</div>
      {right && <div className="toolbar-right">{right}</div>}
    </div>
  );
}
