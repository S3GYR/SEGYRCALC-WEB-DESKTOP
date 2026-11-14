type NativeDialogApi = {
  choose_open_file?: () => Promise<string | null>;
  choose_save_file?: (defaultName?: string) => Promise<string | null>;
  choose_export_file?: (formatName: string, defaultName?: string) => Promise<string | null>;
  choose_export_folder?: (defaultName?: string) => Promise<string | null>;
};

declare global {
  interface Window {
    pywebview?: { api?: NativeDialogApi };
  }
}

export function hasNativeFileDialog(): boolean {
  const disabled = new URLSearchParams(window.location.search).get("native_dialogs") === "0";
  return !disabled && Boolean(window.pywebview?.api?.choose_open_file);
}

export async function chooseOpenFile(): Promise<string | null> {
  const api = window.pywebview?.api;
  if (!api?.choose_open_file) return null;
  return (await api.choose_open_file()) || null;
}

export async function chooseSaveFile(defaultName: string): Promise<string | null> {
  const api = window.pywebview?.api;
  if (!api?.choose_save_file) return null;
  return (await api.choose_save_file(defaultName)) || null;
}

export function hasNativeExportDialog(format: "pdf" | "xlsx" | "csv"): boolean {
  const disabled = new URLSearchParams(window.location.search).get("native_dialogs") === "0";
  const api = window.pywebview?.api;
  return !disabled && (format === "csv" ? Boolean(api?.choose_export_folder) : Boolean(api?.choose_export_file));
}

export async function chooseExportFile(
  format: "pdf" | "xlsx",
  defaultName: string,
): Promise<string | null> {
  const api = window.pywebview?.api;
  if (!api?.choose_export_file) return null;
  return (await api.choose_export_file(format, defaultName)) || null;
}

export async function chooseExportFolder(defaultName: string): Promise<string | null> {
  const api = window.pywebview?.api;
  if (!api?.choose_export_folder) return null;
  return (await api.choose_export_folder(defaultName)) || null;
}
