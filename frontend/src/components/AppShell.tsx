import type { ReactNode } from "react";

export function AppShell({
  sidebar,
  topbar,
  children,
}: {
  sidebar: ReactNode;
  topbar: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="app-shell">
      {sidebar}
      <div className="app-main">
        {topbar}
        <main className="content" data-testid="app-content">
          {children}
        </main>
      </div>
    </div>
  );
}
