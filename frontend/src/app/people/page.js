"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { useLoad } from "@/lib/hooks";
import { ErrorBanner, Field, Loading, Notice, PageHeader } from "@/components/ui";

export default function PeoplePage() {
  const auth = useRequireAuth({ coordinatorOnly: true });
  const people = useLoad(() => (auth.allowed ? api("/users") : Promise.resolve(null)), [auth.allowed]);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "volunteer" });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  if (!auth.allowed) return <Loading />;

  async function create(e) {
    e.preventDefault();
    setError("");
    setNotice("");
    try {
      const user = await api("/users", { method: "POST", body: form });
      setNotice(`Created ${user.role} ${user.name}. Add volunteers to programs from the program page.`);
      setForm({ name: "", email: "", password: "", role: "volunteer" });
      people.reload();
    } catch (err) {
      setError(err.message);
    }
  }
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  return (
    <>
      <PageHeader title="People" subtitle="Everyone with an account. Volunteers can also register themselves." />
      <ErrorBanner message={error || people.error} />
      <Notice message={notice} />
      <form className="card" onSubmit={create}>
        <h2>Create an account</h2>
        <div className="form-grid">
          <Field label="Name"><input value={form.name} onChange={set("name")} required maxLength={120} /></Field>
          <Field label="Email"><input type="email" value={form.email} onChange={set("email")} required /></Field>
          <Field label="Temporary password" hint="At least 8 characters">
            <input type="text" value={form.password} onChange={set("password")} required minLength={8} maxLength={72} />
          </Field>
          <Field label="Role">
            <select value={form.role} onChange={set("role")}>
              <option value="volunteer">Volunteer</option>
              <option value="coordinator">Coordinator</option>
            </select>
          </Field>
          <button className="primary">Create</button>
        </div>
      </form>
      <div className="card">
        {!people.data ? (
          <Loading />
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Name</th><th>Email</th><th>Role</th></tr></thead>
              <tbody>
                {people.data.map((u) => (
                  <tr key={u.id}><td>{u.name}</td><td>{u.email}</td><td>{u.role}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
