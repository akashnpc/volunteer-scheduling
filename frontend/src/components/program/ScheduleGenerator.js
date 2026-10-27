"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { WEEKDAYS, formatDate } from "@/lib/format";
import { ErrorBanner, Field } from "@/components/ui";

const REASONS = {
  excluded_holiday: "Excluded as a holiday",
  already_exists: "A shift already exists at that date and time",
};

export default function ScheduleGenerator({ programId, onGenerated }) {
  const [form, setForm] = useState({
    start_date: "", end_date: "", day_of_week: 0, start_time: "09:00",
    duration_minutes: 120, location: "", required_headcount: 3,
  });
  const [holidays, setHolidays] = useState([]);
  const [holidayInput, setHolidayInput] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  function addHoliday() {
    if (holidayInput && !holidays.includes(holidayInput)) setHolidays([...holidays, holidayInput].sort());
    setHolidayInput("");
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    setResult(null);
    setBusy(true);
    try {
      const data = await api(`/programs/${programId}/schedule`, {
        method: "POST",
        body: {
          ...form,
          day_of_week: Number(form.day_of_week),
          duration_minutes: Number(form.duration_minutes),
          required_headcount: Number(form.required_headcount),
          excluded_dates: holidays,
        },
      });
      setResult(data);
      onGenerated();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>Generate a recurring weekly schedule</h2>
      <p className="muted">Creates one shift every week on the chosen day between the two dates.</p>
      <ErrorBanner message={error} />
      <div className="form-grid">
        <Field label="From"><input type="date" value={form.start_date} onChange={set("start_date")} required /></Field>
        <Field label="Until"><input type="date" value={form.end_date} onChange={set("end_date")} required /></Field>
        <Field label="Day of week">
          <select value={form.day_of_week} onChange={set("day_of_week")}>
            {WEEKDAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
          </select>
        </Field>
        <Field label="Start time"><input type="time" value={form.start_time} onChange={set("start_time")} required /></Field>
        <Field label="Duration (minutes)">
          <input type="number" min="1" max="1440" value={form.duration_minutes} onChange={set("duration_minutes")} required />
        </Field>
        <Field label="Location"><input value={form.location} onChange={set("location")} required maxLength={200} /></Field>
        <Field label="Volunteers needed">
          <input type="number" min="1" value={form.required_headcount} onChange={set("required_headcount")} required />
        </Field>
      </div>

      <div style={{ marginTop: "0.9rem" }}>
        <Field label="Holidays to skip (optional)">
          <div className="row">
            <input type="date" value={holidayInput} onChange={(e) => setHolidayInput(e.target.value)} />
            <button type="button" onClick={addHoliday} disabled={!holidayInput}>Add date</button>
          </div>
        </Field>
        <div className="row" style={{ marginTop: "0.5rem" }}>
          {holidays.map((h) => (
            <span key={h} className="badge" style={{ "--badge": "#6b7280" }}>
              {formatDate(h)}{" "}
              <button type="button" className="link" aria-label={`Remove ${h}`} onClick={() => setHolidays(holidays.filter((x) => x !== h))}>
                x
              </button>
            </span>
          ))}
        </div>
      </div>

      <div style={{ marginTop: "1rem" }}>
        <button className="primary" disabled={busy}>{busy ? "Generating…" : "Generate shifts"}</button>
      </div>

      {result && (
        <div style={{ marginTop: "1rem" }}>
          <h3>Created {result.created.length} shift{result.created.length === 1 ? "" : "s"}</h3>
          <ul>
            {result.created.map((s) => <li key={s.id}>{formatDate(s.date)}</li>)}
          </ul>
          <h3>Skipped {result.skipped.length} date{result.skipped.length === 1 ? "" : "s"}</h3>
          {result.skipped.length === 0 ? (
            <p className="muted">Nothing was skipped.</p>
          ) : (
            <ul>
              {result.skipped.map((s) => <li key={s.date}>{formatDate(s.date)}: {REASONS[s.reason]}</li>)}
            </ul>
          )}
        </div>
      )}
    </form>
  );
}
