type CanvasStatusViewProps = {
  error?: string | null;
};

export function CanvasStatusView({ error }: CanvasStatusViewProps) {
  if (error) {
    return (
      <div className="p-5 text-sm text-[var(--color-danger)]">
        Error: {error}
      </div>
    );
  }

  return (
    <div className="p-5 text-sm text-[var(--color-text-muted)]">
      Loading...
    </div>
  );
}
