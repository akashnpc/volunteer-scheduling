"use client";
import { STATES } from "@/lib/format";

export function StateBadge({ state }) {
  const info = STATES[state] || { label: state, color: "#6b7280" };
  return (
    <span className="badge" style={{ "--badge": info.color }}>
      {info.label}
    </span>
  );
}

export function ErrorBanner({ message, onClose }) {
  if (!message) return null;
  return (
    <div className="banner error" role="alert">
      <span>{message}</span>
      {onClose && (
        <button className="link" onClick={onClose} aria-label="Dismiss message">
          Dismiss
        </button>
      )}
    </div>
  );
}

export function Notice({ message }) {
  if (!message) return null;
  return (
    <div className="banner ok" role="status">
      {message}
    </div>
  );
}

export function Loading({ text = "Loading…" }) {
  return <p className="muted">{text}</p>;
}

export function PageHeader({ title, children, subtitle }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      <div className="row">{children}</div>
    </div>
  );
}

export function Pagination({ page, pages, total, pageSize, onPage }) {
  if (!total) return null;
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);
  return (
    <div className="pagination">
      <span className="muted">
        Showing {first}&ndash;{last} of {total} matching shift{total === 1 ? "" : "s"}
      </span>
      <div className="row">
        <button onClick={() => onPage(page - 1)} disabled={page <= 1}>
          Previous
        </button>
        <span>
          Page {page} of {pages}
        </span>
        <button onClick={() => onPage(page + 1)} disabled={page >= pages}>
          Next
        </button>
      </div>
    </div>
  );
}

export function Field({ label, children, hint }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small className="muted">{hint}</small>}
    </label>
  );
}
