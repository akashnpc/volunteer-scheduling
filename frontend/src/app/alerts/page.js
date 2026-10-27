"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { useLoad } from "@/lib/hooks";
import { formatDate, formatRange } from "@/lib/format";
import { ErrorBanner, Loading, PageHeader, StateBadge } from "@/components/ui";

function daysAway(dateString) {
  const [y, m, d] = dateString.split("-").map(Number);
  const today = new Date();
  const diff = Math.round((new Date(y, m - 1, d) - new Date(today.getFullYear(), today.getMonth(), today.getDate())) / 86400000);
  return diff <= 0 ? "today" : diff === 1 ? "tomorrow" : `in ${diff} days`;
}

export default function AlertsPage() {
  const auth = useRequireAuth();
  const alerts = useLoad(() => (auth.allowed ? api("/alerts") : Promise.resolve(null)), [auth.allowed]);
  const [error, setError] = useState("");

  if (!auth.allowed) return <Loading />;

  async function dismiss(shiftId) {
    setError("");
    try {
      await api(`/alerts/${shiftId}/dismiss`, { method: "POST" });
      alerts.reload();
    } catch (e) {
      setError(e.message);
    }
  }

  const items = alerts.data?.items || [];
  const active = items.filter((a) => !a.dismissed);
  const dismissed = items.filter((a) => a.dismissed);

  const row = (a, canDismiss) => (
    <tr key={a.id}>
      <td>
        <Link href={`/shifts/${a.id}`}>{formatDate(a.date)}</Link> <small className="muted">({daysAway(a.date)})</small>
      </td>
      <td>{formatRange(a)}</td>
      <td>{a.program_name}</td>
      <td>{a.location}</td>
      <td>{a.signup_count}/{a.required_headcount} ({a.spots_left} still needed)</td>
      <td><StateBadge state={a.state} /></td>
      <td>
        {canDismiss && auth.isCoordinator && <button onClick={() => dismiss(a.id)}>Dismiss</button>}
      </td>
    </tr>
  );
  const head = (
    <thead>
      <tr><th>Date</th><th>Time</th><th>Program</th><th>Location</th><th>Filled</th><th>Status</th><th /></tr>
    </thead>
  );

  return (
    <>
      <PageHeader
        title="Understaffed shifts"
        subtitle="Open or partially filled shifts happening in the next 3 days. A dismissed alert comes back if a cancellation un-fills the shift."
      />
      <ErrorBanner message={error || alerts.error} />
      {!alerts.data ? (
        <Loading />
      ) : (
        <>
          <div className="card">
            <h2>Needs attention ({active.length})</h2>
            {active.length === 0 ? (
              <p className="muted">Nothing is understaffed right now.</p>
            ) : (
              <div className="table-wrap"><table>{head}<tbody>{active.map((a) => row(a, true))}</tbody></table></div>
            )}
          </div>
          {dismissed.length > 0 && (
            <div className="card">
              <h2>Dismissed ({dismissed.length})</h2>
              <div className="table-wrap"><table>{head}<tbody>{dismissed.map((a) => row(a, false))}</tbody></table></div>
            </div>
          )}
        </>
      )}
    </>
  );
}
