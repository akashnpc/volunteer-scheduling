"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { formatDate, formatDuration, formatRange } from "@/lib/format";
import { ErrorBanner, StateBadge } from "@/components/ui";

/**
 * A list of shifts. Volunteers get Sign up / Cancel buttons here; coordinators manage from the
 * shift page. Server rejections (overlap, filled, closed...) are shown verbatim.
 */
export default function ShiftTable({ shifts, user, onChanged, showProgram = true }) {
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  async function act(shift, action) {
    setError("");
    setBusyId(shift.id);
    try {
      if (action === "signup") await api(`/shifts/${shift.id}/signups`, { method: "POST", body: {} });
      else await api(`/signups/${shift.my_signup_id}`, { method: "DELETE" });
      onChanged();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  }

  if (!shifts.length) return <p className="muted">No shifts match.</p>;
  const isVolunteer = user.role === "volunteer";

  return (
    <>
      <ErrorBanner message={error} onClose={() => setError("")} />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Time</th>
              {showProgram && <th>Program</th>}
              <th>Location</th>
              <th>Filled</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {shifts.map((s) => (
              <tr key={s.id}>
                <td>
                  <Link href={`/shifts/${s.id}`}>{formatDate(s.date)}</Link>
                </td>
                <td>
                  {formatRange(s)} <small className="muted">({formatDuration(s.duration_minutes)})</small>
                </td>
                {showProgram && <td>{s.program_name}</td>}
                <td>{s.location}</td>
                <td>
                  <span className="meter" aria-hidden="true">
                    <span style={{ width: `${Math.min(100, (s.signup_count / s.required_headcount) * 100)}%` }} />
                  </span>
                  {s.signup_count}/{s.required_headcount}
                </td>
                <td>
                  <StateBadge state={s.state} />
                </td>
                <td>
                  {isVolunteer && s.my_signup_id && s.state !== "closed" && (
                    <button disabled={busyId === s.id} onClick={() => act(s, "cancel")}>
                      Cancel my signup
                    </button>
                  )}
                  {isVolunteer && !s.my_signup_id && (s.state === "open" || s.state === "partially_filled") && (
                    <button className="primary" disabled={busyId === s.id} onClick={() => act(s, "signup")}>
                      Sign up
                    </button>
                  )}
                  {isVolunteer && s.my_signup_id && s.state === "closed" && <small className="muted">You worked this</small>}
                  {!isVolunteer && (
                    <Link className="button" href={`/shifts/${s.id}`}>
                      Manage
                    </Link>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
