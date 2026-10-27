"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { useLoad } from "@/lib/hooks";
import { formatDate, formatDateTime, formatDuration, formatRange } from "@/lib/format";
import Timeline from "@/components/Timeline";
import { ErrorBanner, Field, Loading, PageHeader, StateBadge } from "@/components/ui";

export default function ShiftPage() {
  const { id } = useParams();
  const router = useRouter();
  const auth = useRequireAuth();
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(null);
  const [pick, setPick] = useState("");
  const [note, setNote] = useState("");

  const shift = useLoad(() => (auth.allowed ? api(`/shifts/${id}`) : Promise.resolve(null)), [auth.allowed, id]);
  const timeline = useLoad(() => (auth.allowed ? api(`/shifts/${id}/timeline`) : Promise.resolve(null)), [auth.allowed, id]);
  const programId = shift.data?.program_id;
  const members = useLoad(
    () => (auth.isCoordinator && programId ? api(`/programs/${programId}/members`) : Promise.resolve([])),
    [auth.isCoordinator, programId],
  );

  if (!auth.allowed) return <Loading />;
  const s = shift.data;
  if (!s) return shift.error ? <ErrorBanner message={shift.error} /> : <Loading />;

  const refresh = () => {
    shift.reload();
    timeline.reload();
  };

  async function run(action) {
    setError("");
    try {
      await action();
      refresh();
    } catch (e) {
      setError(e.message);
    }
  }

  const closed = s.state === "closed";
  const canSignUp = !s.my_signup_id && (s.state === "open" || s.state === "partially_filled");
  const signedIds = new Set(s.signups.map((x) => x.volunteer_id));
  const addable = (members.data || []).filter((m) => !signedIds.has(m.id));
  const set = (key) => (e) => setDraft({ ...draft, [key]: e.target.value });

  function startEdit() {
    setDraft({
      date: s.date, start_time: s.start_time.slice(0, 5), duration_minutes: s.duration_minutes,
      location: s.location, required_headcount: s.required_headcount,
    });
    setEditing(!editing);
  }

  return (
    <>
      <PageHeader
        title={`${s.program_name}: ${formatDate(s.date)}`}
        subtitle={`${formatRange(s)} (${formatDuration(s.duration_minutes)}) at ${s.location}`}
      >
        <StateBadge state={s.state} />
        <Link className="button" href={`/programs/${s.program_id}`}>Back to program</Link>
      </PageHeader>
      <ErrorBanner message={error || shift.error} onClose={() => setError("")} />

      <section className="card">
        <h2>Signups: {s.signup_count} of {s.required_headcount} ({s.spots_left} still needed)</h2>

        {!auth.isCoordinator && (
          <div className="row" style={{ marginBottom: "0.8rem" }}>
            {canSignUp && (
              <button className="primary" onClick={() => run(() => api(`/shifts/${id}/signups`, { method: "POST", body: {} }))}>
                Sign up for this shift
              </button>
            )}
            {s.my_signup_id && !closed && (
              <button onClick={() => run(() => api(`/signups/${s.my_signup_id}`, { method: "DELETE" }))}>
                Cancel my signup
              </button>
            )}
            {s.my_signup_id && <span className="muted">You are signed up for this shift.</span>}
          </div>
        )}

        {auth.isCoordinator && !closed && (
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
                  await api(`/shifts/${id}/signups`, { method: "POST", body: { volunteer_id: Number(pick) } });
                  setPick("");
                })
              }
            >
              Sign up
            </button>
          </div>
        )}

        {s.signups.length === 0 ? (
          <p className="muted">{auth.isCoordinator ? "Nobody has signed up yet." : "You are not signed up."}</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Volunteer</th><th>Signed up</th><th /></tr></thead>
              <tbody>
                {s.signups.map((x) => (
                  <tr key={x.id}>
                    <td>{x.volunteer_name} <small className="muted">{x.volunteer_email}</small></td>
                    <td>{formatDateTime(x.created_at)}</td>
                    <td>
                      {auth.isCoordinator && !closed && (
                        <button className="danger" onClick={() => run(() => api(`/signups/${x.id}`, { method: "DELETE" }))}>
                          Cancel signup
                        </button>
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

      {auth.isCoordinator && (
        <section className="card">
          <h2>Coordinator actions</h2>
          <div className="row">
            {!closed && <button onClick={startEdit}>{editing ? "Cancel editing" : "Edit shift"}</button>}
            {!closed && (
              <button onClick={() => run(() => api(`/shifts/${id}/close`, { method: "POST" }))}>
                Close shift
              </button>
            )}
            {!closed && (
              <button
                className="danger"
                onClick={() => {
                  if (confirm("Delete this shift? Any signups will be cancelled. Its history is kept.")) {
                    api(`/shifts/${id}`, { method: "DELETE" })
                      .then(() => router.replace(`/programs/${s.program_id}`))
                      .catch((e) => setError(e.message));
                  }
                }}
              >
                Delete shift
              </button>
            )}
          </div>
          {!closed && <p className="muted">A shift can be closed once its scheduled time has passed.</p>}
          {editing && draft && (
            <form
              style={{ marginTop: "1rem" }}
              onSubmit={(e) => {
                e.preventDefault();
                run(async () => {
                  await api(`/shifts/${id}`, {
                    method: "PATCH",
                    body: {
                      ...draft,
                      duration_minutes: Number(draft.duration_minutes),
                      required_headcount: Number(draft.required_headcount),
                    },
                  });
                  setEditing(false);
                });
              }}
            >
              <div className="form-grid">
                <Field label="Date"><input type="date" value={draft.date} onChange={set("date")} required /></Field>
                <Field label="Start time"><input type="time" value={draft.start_time} onChange={set("start_time")} required /></Field>
                <Field label="Duration (minutes)">
                  <input type="number" min="1" max="1440" value={draft.duration_minutes} onChange={set("duration_minutes")} required />
                </Field>
                <Field label="Location"><input value={draft.location} onChange={set("location")} required /></Field>
                <Field label="Volunteers needed">
                  <input type="number" min="1" value={draft.required_headcount} onChange={set("required_headcount")} required />
                </Field>
                <button className="primary">Save changes</button>
              </div>
            </form>
          )}
        </section>
      )}

      <section className="card">
        <h2>History</h2>
        <p className="muted">Entries cannot be edited or deleted, by anyone.</p>
        {auth.isCoordinator && (
          <form
            className="row"
            style={{ marginBottom: "1rem" }}
            onSubmit={(e) => {
              e.preventDefault();
              run(async () => {
                await api(`/shifts/${id}/notes`, { method: "POST", body: { message: note } });
                setNote("");
              });
            }}
          >
            <input
              style={{ flex: 1, minWidth: 200 }}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Add a note to this shift's history"
              maxLength={2000}
              aria-label="Note"
            />
            <button className="primary" disabled={!note.trim()}>Add note</button>
          </form>
        )}
        {timeline.error && <ErrorBanner message={timeline.error} />}
        {timeline.data ? <Timeline events={timeline.data} /> : <Loading />}
      </section>
    </>
  );
}
