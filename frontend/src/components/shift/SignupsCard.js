"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

// Who is signed up, plus the sign-up / cancel controls for the current role.
// `run` runs an API call, shows its error in the page banner and reloads the page data.
export default function SignupsCard({ shift, isCoordinator, members, run }) {
  const [pick, setPick] = useState("");
  const closed = shift.state === "closed";
  const canSignUp = !shift.my_signup_id && (shift.state === "open" || shift.state === "partially_filled");
  const signedIds = new Set(shift.signups.map((x) => x.volunteer_id));
  const addable = members.filter((m) => !signedIds.has(m.id));
  const cancelSignup = (signupId) => run(() => api(`/signups/${signupId}`, { method: "DELETE" }));

  return (
    <section className="card">
      <h2>Signups: {shift.signup_count} of {shift.required_headcount} ({shift.spots_left} still needed)</h2>

      {!isCoordinator && (
        <div className="row" style={{ marginBottom: "0.8rem" }}>
          {canSignUp && (
            <button className="primary" onClick={() => run(() => api(`/shifts/${shift.id}/signups`, { method: "POST", body: {} }))}>
              Sign up for this shift
            </button>
          )}
          {shift.my_signup_id && !closed && <button onClick={() => cancelSignup(shift.my_signup_id)}>Cancel my signup</button>}
          {shift.my_signup_id && <span className="muted">You are signed up for this shift.</span>}
        </div>
      )}

      {isCoordinator && !closed && (
        <div className="row" style={{ marginBottom: "0.8rem" }}>
          <select value={pick} onChange={(e) => setPick(e.target.value)} aria-label="Volunteer to sign up">
            <option value="">Sign up a volunteer&hellip;</option>
            {addable.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
          <button
            className="primary"
            disabled={!pick}
            onClick={() =>
              run(async () => {
                await api(`/shifts/${shift.id}/signups`, { method: "POST", body: { volunteer_id: Number(pick) } });
                setPick("");
              })
            }
          >
            Sign up
          </button>
        </div>
      )}

      {shift.signups.length === 0 ? (
        <p className="muted">{isCoordinator ? "Nobody has signed up yet." : "You are not signed up."}</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Volunteer</th><th>Signed up</th><th /></tr></thead>
            <tbody>
              {shift.signups.map((x) => (
                <tr key={x.id}>
                  <td>{x.volunteer_name} <small className="muted">{x.volunteer_email}</small></td>
                  <td>{formatDateTime(x.created_at)}</td>
                  <td>
                    {isCoordinator && !closed && (
                      <button className="danger" onClick={() => cancelSignup(x.id)}>Cancel signup</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {closed && <p className="muted">This shift is closed. Signups and cancellations are locked.</p>}
    </section>
  );
}
