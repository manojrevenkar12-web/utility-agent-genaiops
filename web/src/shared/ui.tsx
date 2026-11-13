import type { ReactNode } from "react";
import { skeletonStep } from "../app/theme";

export function Section({ id, title, lede, children }: { id: string; title: string; lede: string; children: ReactNode }) {
  return (
    <section className="section" aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      <p className="lede">{lede}</p>
      {children}
    </section>
  );
}

export function Skeleton({ rows }: { rows: number }) {
  return (
    <div className="panel state" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton" style={{ width: `${100 - i * skeletonStep}%` }} />
      ))}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="panel state" role="alert">
      <strong>The run data did not load.</strong>
      <span className="muted">
        {message}. Run python3 scripts/readme.py to write web/public/data/console.json, then retry.
      </span>
      <button onClick={onRetry}>Retry</button>
    </div>
  );
}

export const Empty = ({ children }: { children: ReactNode }) => <div className="panel state muted">{children}</div>;
