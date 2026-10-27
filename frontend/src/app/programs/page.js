"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { useLoad } from "@/lib/hooks";
import { ErrorBanner, Field, Loading, PageHeader } from "@/components/ui";

export default function ProgramsPage() {
  const auth = useRequireAuth();
  const [showArchived, setShowArchived] = useState(false);
  const [form, setForm] = useState({ name: "", description: "" });
  const [error, setError] = useState("");
  const programs = useLoad(
    () => (auth.allowed ? api("/programs", { params: { include_archived: showArchived } }) : Promise.resolve(null)),
    [auth.allowed, showArchived],
  );

  if (!auth.allowed) return <Loading />;

  async function create(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/programs", { method: "POST", body: form });
      setForm({ name: "", description: "" });
      programs.reload();
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleArchive(program) {
    setError("");
    try {
      await api(`/programs/${program.id}/${program.archived ? "restore" : "archive"}`, { method: "POST" });
      programs.reload();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <PageHeader
        title="Programs"
        subtitle={auth.isCoordinator ? "Create programs, then add shifts and volunteers." : "The programs you belong to."}
      >
        {auth.isCoordinator && (
          <label className="row">
            <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
            Show archived
          </label>
        )}
      </PageHeader>
      <ErrorBanner message={error || programs.error} onClose={() => setError("")} />

      {auth.isCoordinator && (
        <form className="card" onSubmit={create}>
          <h2>New program</h2>
          <div className="form-grid">
            <Field label="Name">
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required maxLength={120} />
            </Field>
            <Field label="Description">
              <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} maxLength={2000} />
            </Field>
            <button className="primary">Create program</button>
          </div>
        </form>
      )}

      {!programs.data ? (
        <Loading />
      ) : programs.data.length === 0 ? (
        <p className="muted" style={{ marginTop: "1rem" }}>
          {auth.isCoordinator ? "No programs yet." : "You have not been added to any programs yet. Ask a coordinator."}
        </p>
      ) : (
        <div className="grid cols-2" style={{ marginTop: "1rem" }}>
          {programs.data.map((p) => (
            <div className="card" key={p.id}>
              <h2>
                <Link href={`/programs/${p.id}`}>{p.name}</Link>{" "}
                {p.archived && <span className="badge" style={{ "--badge": "#6b7280" }}>Archived</span>}
              </h2>
              <p className="muted">{p.description || "No description."}</p>
              <p>
                {p.shift_count} shift{p.shift_count === 1 ? "" : "s"} &middot; {p.member_count} volunteer
                {p.member_count === 1 ? "" : "s"}
              </p>
              <div className="row">
                <Link className="button" href={`/programs/${p.id}`}>Open</Link>
                {auth.isCoordinator && (
                  <button onClick={() => toggleArchive(p)}>{p.archived ? "Restore" : "Archive"}</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
