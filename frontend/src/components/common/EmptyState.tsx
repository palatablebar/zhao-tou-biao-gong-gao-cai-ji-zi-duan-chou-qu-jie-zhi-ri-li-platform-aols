interface EmptyStateProps {
  title: string;
  hint: string;
  actionLabel?: string;
  onAction?: () => void;
}

export default function EmptyState({ title, hint, actionLabel, onAction }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <div className="empty-rule" aria-hidden="true" />
      <h3>{title}</h3>
      <p>{hint}</p>
      {actionLabel && onAction ? (
        <button className="btn btn-sm" type="button" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}
