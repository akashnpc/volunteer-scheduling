"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import { api, download } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { useLoad } from "@/lib/hooks";
import ShiftTable from "@/components/ShiftTable";
import Members from "@/components/program/Members";
import NewShiftForm from "@/components/program/NewShiftForm";
import ScheduleGenerator from "@/components/program/ScheduleGenerator";
import { ErrorBanner, Field, Loading, PageHeader, Pagination } from "@/components/ui";

const PAGE_SIZE = 10;

export default function ProgramPage() {
  const { id } = useParams();
  const auth = useRequireAuth();
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({ name: "", description: "" });
  const [error, setError] = useState("");

  const program = useLoad(() => (auth.allowed ? api(`/programs/${id}`) : Promise.resolve(null)), [auth.allowed, id]);
  const shifts = useLoad(
    () =>
      auth.allowed
        ? api("/shifts", { params: { program_id: id, include_archived: true, page, page_size: PAGE_SIZE } })
        : Promise.resolve(null),
    [auth.allowed, id, page],
  );

  if (!auth.allowed) return <Loading />;
  const p = program.data;
  if (!p) return program.error ? <ErrorBanner message={program.error} /> : <Loading />;

  const refresh = () => {
    program.reload();
    shifts.reload();
  };

  async function save(e) {
    e.preventDefault();
    setError("");
    try {
      await api(`/programs/${id}`, { method: "PATCH", body: draft });
      setEditing(false);
      program.reload();
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleArchive() {
    setError("");
    try {
      await api(`/programs/${id}/${p.archived ? "restore" : "archive"}`, { method: "POST" });
      program.reload();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <PageHeader
        title={p.name + (p.archived ? " (archived)" : "")}
        subtitle={`${p.shift_count} shifts · ${p.member_count} volunteers`}
      >
        {auth.isCoordinator && (
          <>
            <button onClick={() => { setDraft({ name: p.name, description: p.description }); setEditing(!editing); }}>
              {editing ? "Cancel editing" : "Edit details"}
            </button>
            <button onClick={toggleArchive}>{p.archived ? "Restore program" : "Archive program"}</button>
            <button onClick={() => download(`/programs/${id}/roster.csv`, "roster.csv").catch((e) => setError(e.message))}>
              Export roster (CSV)
            </button>
          </>
        )}
      </PageHeader>
      <ErrorBanner message={error} onClose={() => setError("")} />

      {editing ? (
        <form className="card" onSubmit={save}>
          <div className="form-grid">
            <Field label="Name">
              <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} required maxLength={120} />
            </Field>
            <Field label="Description">
              <input value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} maxLength={2000} />
            </Field>
            <button className="primary">Save</button>
          </div>
        </form>
      ) : (
        <p>{p.description || <span className="muted">No description.</span>}</p>
      )}

      <section className="card">
        <h2>Shifts</h2>
        <ErrorBanner message={shifts.error} />
        {!shifts.data ? (
          <Loading />
        ) : (
          <>
            <ShiftTable shifts={shifts.data.items} user={auth.user} onChanged={refresh} showProgram={false} />
            <Pagination
              page={shifts.data.page}
              pages={shifts.data.pages}
              total={shifts.data.total}
              pageSize={shifts.data.page_size}
              onPage={setPage}
            />
          </>
        )}
      </section>

      {auth.isCoordinator && (
        <>
          <NewShiftForm programId={Number(id)} onCreated={refresh} />
          <ScheduleGenerator programId={Number(id)} onGenerated={refresh} />
          <Members programId={id} onChanged={refresh} />
        </>
      )}
    </>
  );
}
