export function LoadingState({ label }: { label: string }) {
  return (
    <div className="loading-state" data-testid="loading-state" role="status">
      <span className="spinner" />
      <strong>{label}</strong>
      <span>Le moteur Python local est sollicité en lecture seule.</span>
    </div>
  );
}
