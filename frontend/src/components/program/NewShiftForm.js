"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { ErrorBanner, Field } from "@/components/ui";

const todayIso = () => new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD in local time

export default function NewShiftForm({ programId, onCreated }) {
  const [form, setForm] = useState({
    date: todayIso(), start_time: "09:00", duration_minutes: 120, location: "", required_headcount: 3,
  });
  const [error, setError] = useState("");
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      await api("/shifts", {
        method: "POST",
        body: {
          ...form,
          program_id: programId,
          duration_minutes: Number(form.duration_minutes),
          required_headcount: Number(form.required_headcount),
        },
      });
      onCreated();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>Add a shift</h2>
      <ErrorBanner message={error} />
      <div className="form-grid">
        <Field label="Date"><input type="date" value={form.date} onChange={set("date")} required /></Field>
        <Field label="Start time"><input type="time" value={form.start_time} onChange={set("start_time")} required /></Field>
        <Field label="Duration (minutes)">
          <input type="number" min="1" max="1440" value={form.duration_minutes} onChange={set("duration_minutes")} required />
        </Field>
        <Field label="Location"><input value={form.location} onChange={set("location")} required maxLength={200} /></Field>
        <Field label="Volunteers needed">
          <input type="number" min="1" max="1000" value={form.required_headcount} onChange={set("required_headcount")} required />
        </Field>
        <button className="primary">Add shift</button>
      </div>
    </form>
  );
}
