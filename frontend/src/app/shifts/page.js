"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { useDebounced, useLoad } from "@/lib/hooks";
import { STATES } from "@/lib/format";
import ShiftTable from "@/components/ShiftTable";
import { ErrorBanner, Field, Loading, PageHeader, Pagination } from "@/components/ui";

const PAGE_SIZE = 15;

export default function ShiftsPage() {
  const auth = useRequireAuth();
  // Start on upcoming shifts; "Clear filters" shows every date including past (closable) shifts.
  const [filters, setFilters] = useState({
    q: "", program_id: "", state: "", date_from: new Date().toLocaleDateString("en-CA"), date_to: "",
    sort: "date", order: "asc", mine: false,
  });
  const [page, setPage] = useState(1);
  const q = useDebounced(filters.q);

  const programs = useLoad(() => (auth.allowed ? api("/programs") : Promise.resolve([])), [auth.allowed]);
  const shifts = useLoad(
    () =>
      auth.allowed
        ? api("/shifts", { params: { ...filters, q, page, page_size: PAGE_SIZE } })
        : Promise.resolve(null),
    [auth.allowed, q, filters.program_id, filters.state, filters.date_from, filters.date_to,
      filters.sort, filters.order, filters.mine, page],
  );

  if (!auth.allowed) return <Loading />;

  const change = (key) => (e) => {
    const value = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setFilters({ ...filters, [key]: value });
    setPage(1);
  };
  const reset = () => {
    setFilters({ q: "", program_id: "", state: "", date_from: "", date_to: "", sort: "date", order: "asc", mine: false });
    setPage(1);
  };
  const result = shifts.data;

  return (
    <>
      <PageHeader title="Shifts" subtitle="Every shift in the programs you can see. Search, filter and sort run on the server." />
      <div className="card filters">
        <div className="form-grid">
          <Field label="Search program or location">
            <input value={filters.q} onChange={change("q")} placeholder="e.g. pantry, library" />
          </Field>
          <Field label="Program">
            <select value={filters.program_id} onChange={change("program_id")}>
              <option value="">All programs</option>
              {(programs.data || []).map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </Field>
          <Field label="Fill state">
            <select value={filters.state} onChange={change("state")}>
              <option value="">Any</option>
              {Object.entries(STATES).map(([value, s]) => (
                <option key={value} value={value}>{s.label}</option>
              ))}
            </select>
          </Field>
          <Field label="From date">
            <input type="date" value={filters.date_from} onChange={change("date_from")} />
          </Field>
          <Field label="To date">
            <input type="date" value={filters.date_to} onChange={change("date_to")} />
          </Field>
          <Field label="Sort by">
            <select value={filters.sort} onChange={change("sort")}>
              <option value="date">Date</option>
              <option value="start_time">Start time</option>
              <option value="state">Fill state</option>
            </select>
          </Field>
          <Field label="Order">
            <select value={filters.order} onChange={change("order")}>
              <option value="asc">Ascending</option>
              <option value="desc">Descending</option>
            </select>
          </Field>
          {!auth.isCoordinator && (
            <label className="row">
              <input type="checkbox" checked={filters.mine} onChange={change("mine")} /> Only my shifts
            </label>
          )}
          <button onClick={reset}>Clear filters</button>
        </div>
      </div>

      <ErrorBanner message={shifts.error} />
      <div className="card">
        {!result ? (
          <Loading />
        ) : (
          <>
            <ShiftTable shifts={result.items} user={auth.user} onChanged={shifts.reload} />
            <Pagination
              page={result.page}
              pages={result.pages}
              total={result.total}
              pageSize={result.page_size}
              onPage={setPage}
            />
          </>
        )}
      </div>
    </>
  );
}
