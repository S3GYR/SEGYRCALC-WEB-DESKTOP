import { Component, StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { diag, installGlobalDiagnostics } from "./diagnostics";
import "./styles.css";
import "./styles-v2.css";

installGlobalDiagnostics();

class RootErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string }) {
    diag("react_error", {
      message: String(error.message || ""),
      component_stack: String(info.componentStack || ""),
    });
  }

  render() {
    if (this.state.error) {
      return (
        <div className="boot-fallback boot-fallback-error" data-testid="boot-error">
          <strong>SEGYRCALC n’a pas pu afficher l’interface.</strong>
          <span>{this.state.error.message}</span>
        </div>
      );
    }
    return this.props.children;
  }
}

const root = document.getElementById("root");
if (!root) {
  diag("root_missing");
} else {
  diag("react_mount_start");
  createRoot(root).render(
    <StrictMode>
      <RootErrorBoundary>
        <App />
      </RootErrorBoundary>
    </StrictMode>,
  );
  diag("react_mount_done");
  window.setTimeout(() => {
    diag("dom_after_render", {
      root_children: root.childElementCount,
      root_text_length: (root.innerText || "").length,
    });
  }, 0);
}
