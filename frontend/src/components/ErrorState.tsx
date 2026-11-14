import { Icon } from "../icons";

export function ErrorState({
  title = "Une erreur locale est survenue",
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="error-state" role="alert" data-testid="error-state">
      <span className="error-state-icon"><Icon name="alert" size={22} /></span>
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
        {onRetry && (
          <button type="button" className="button button-secondary" onClick={onRetry}>
            <Icon name="reset" size={15} />
            Réessayer
          </button>
        )}
      </div>
    </div>
  );
}
