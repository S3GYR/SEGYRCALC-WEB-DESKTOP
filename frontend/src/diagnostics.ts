const token = document
  .querySelector<HTMLMetaElement>('meta[name="segyr-session-token"]')
  ?.content.trim();

type DiagnosticData = Record<string, unknown>;

export function diag(event: string, data: DiagnosticData = {}): void {
  if (!token || token === "__SEGYR_SESSION_TOKEN__") return;
  const payload = {
    event,
    time: typeof performance !== "undefined" ? performance.now() : 0,
    data,
  };
  try {
    void fetch("/api/diagnostics/client", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-SEGYR-Token": token,
      },
      body: JSON.stringify(payload),
    }).catch(() => undefined);
  } catch {
    // Diagnostics must never break the application.
  }
}

export function installGlobalDiagnostics(): void {
  window.addEventListener("error", (event) => {
    diag("window_error", {
      message: String(event.message || ""),
      source: String(event.filename || ""),
      line: event.lineno,
      column: event.colno,
    });
  });
  window.addEventListener("unhandledrejection", (event) => {
    diag("unhandled_rejection", {
      message: String((event.reason as { message?: string } | undefined)?.message ?? event.reason ?? ""),
    });
  });
  diag("js_boot");
}
