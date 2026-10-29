"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import Timeline from "@/components/Timeline";
import { ErrorBanner, Loading } from "@/components/ui";

// The append-only timeline. Coordinators can add notes; nobody can edit or delete entries.
export default function HistoryCard({ shiftId, isCoordinator, timeline, run }) {
  const [note, setNote] = useState("");

  function addNote(e) {
    e.preventDefault();
    run(async () => {
      await api(`/shifts/${shiftId}/notes`, { method: "POST", body: { message: note } });
      setNote("");
    });
  }

  return (
    <section className="card">
      <h2>History</h2>
      <p className="muted">Entries cannot be edited or deleted, by anyone.</p>
      {isCoordinator && (
        <form className="row" style={{ marginBottom: "1rem" }} onSubmit={addNote}>
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
  );
}
