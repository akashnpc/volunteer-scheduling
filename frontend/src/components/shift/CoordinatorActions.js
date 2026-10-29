"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { Field } from "@/components/ui";

const editDraft = (shift) => ({
  date: shift.date,
  start_time: shift.start_time.slice(0, 5),
  duration_minutes: shift.duration_minutes,
  location: shift.location,
  required_headcount: shift.required_headcount,
});

// Edit, close and delete a shift. Hidden once the shift is closed (the server refuses it too).
export default function CoordinatorActions({ shift, run, onDelete }) {
  const [draft, setDraft] = useState(null); // null = edit form closed
  const set = (key) => (e) => setDraft({ ...draft, [key]: e.target.value });

  function save(e) {
    e.preventDefault();
    run(async () => {
      await api(`/shifts/${shift.id}`, {
        method: "PATCH",
        body: {
          ...draft,
          duration_minutes: Number(draft.duration_minutes),
          required_headcount: Number(draft.required_headcount),
        },
      });
      setDraft(null);
    });
  }

  const closed = shift.state === "closed";
  return (
    <section className="card">
      <h2>Coordinator actions</h2>
      {!closed && (
        <>
          <div className="row">
            <button onClick={() => setDraft(draft ? null : editDraft(shift))}>{draft ? "Cancel editing" : "Edit shift"}</button>
            <button onClick={() => run(() => api(`/shifts/${shift.id}/close`, { method: "POST" }))}>Close shift</button>
            <button
              className="danger"
              onClick={() => {
                if (confirm("Delete this shift? Any signups will be cancelled. Its history is kept.")) onDelete();
              }}
            >
              Delete shift
            </button>
          </div>
          <p className="muted">A shift can be closed once its scheduled time has passed.</p>
        </>
      )}
      {draft && (
        <form style={{ marginTop: "1rem" }} onSubmit={save}>
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
  );
}
