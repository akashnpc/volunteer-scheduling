"use client";
import Link from "next/link";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { useLoad } from "@/lib/hooks";
import { STATES, formatShortDate } from "@/lib/format";
import { ErrorBanner, Loading, PageHeader } from "@/components/ui";

function Stat({ value, label }) {
  return (
    <div className="card stat">
      <div className="value">{value}</div>
      <div className="label">{label}</div>
    </div>
  );
}

export default function DashboardPage() {
  const auth = useRequireAuth();
  const dash = useLoad(() => (auth.allowed ? api("/dashboard") : Promise.resolve(null)), [auth.allowed]);
  const d = dash.data;

  if (!auth.allowed) return <Loading />;

  const stateData = d && Object.entries(STATES).map(([key, s]) => ({
    name: s.label, value: d.by_state[key], color: s.color,
  }));
  const weekly = d && d.signups_per_week.map((w) => ({ week: formatShortDate(w.week_start), signups: w.signups }));

  return (
    <>
      <PageHeader
        title={`Hello, ${auth.user.name.split(" ")[0]}`}
        subtitle={d && `Week of ${formatShortDate(d.week_start)} to ${formatShortDate(d.week_end)}`}
      >
        <Link className="button primary" href="/shifts">Browse shifts</Link>
        <Link className="button" href="/alerts">Understaffed alerts</Link>
      </PageHeader>
      <ErrorBanner message={dash.error} />
      {!d ? (
        <Loading />
      ) : (
        <>
          <div className="grid cols-4">
            <Stat value={d.shifts_this_week} label="Shifts this week" />
            <Stat value={d.open_shifts_this_week} label="Open shifts this week (no signups yet)" />
            <Stat value={d.signups_this_week} label="Signups made this week" />
            <Stat value={d.shifts_closed_this_week} label="Shifts closed this week" />
          </div>

          <div className="grid cols-2" style={{ marginTop: "1rem" }}>
            <section className="card">
              <h2>Signups per week (last 8 weeks)</h2>
              <div style={{ width: "100%", height: 260 }}>
                <ResponsiveContainer>
                  <BarChart data={weekly} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="week" fontSize={12} />
                    <YAxis allowDecimals={false} fontSize={12} />
                    <Tooltip />
                    <Bar dataKey="signups" name="Signups" fill="#0f766e" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section className="card">
              <h2>Shifts by fill state</h2>
              <div style={{ width: "100%", height: 260 }}>
                <ResponsiveContainer>
                  <BarChart data={stateData} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" fontSize={12} />
                    <YAxis allowDecimals={false} fontSize={12} />
                    <Tooltip />
                    <Bar dataKey="value" name="Shifts" radius={[4, 4, 0, 0]}>
                      {stateData.map((s) => <Cell key={s.name} fill={s.color} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
          </div>

          <section className="card">
            <h2>Shifts by program</h2>
            {d.by_program.length === 0 ? (
              <p className="muted">No programs yet.</p>
            ) : (
              <div style={{ width: "100%", height: Math.max(180, d.by_program.length * 56 + 60) }}>
                <ResponsiveContainer>
                  <BarChart data={d.by_program} layout="vertical" margin={{ top: 8, right: 16, bottom: 0, left: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" allowDecimals={false} fontSize={12} />
                    <YAxis type="category" dataKey="program_name" width={150} fontSize={12} />
                    <Tooltip />
                    <Legend />
                    {Object.entries(STATES).map(([key, s]) => (
                      <Bar key={key} dataKey={key} name={s.label} stackId="a" fill={s.color} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </section>
        </>
      )}
    </>
  );
}
