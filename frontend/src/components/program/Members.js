"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { useLoad } from "@/lib/hooks";
import { ErrorBanner, Loading } from "@/components/ui";

export default function Members({ programId, onChanged }) {
  const members = useLoad(() => api(`/programs/${programId}/members`), [programId]);
  const volunteers = useLoad(() => api("/users", { params: { role: "volunteer" } }), []);
  const [choice, setChoice] = useState("");
  const [error, setError] = useState("");

  async function run(action) {
    setError("");
    try {
      await action();
      members.reload();
      onChanged();
    } catch (e) {
      setError(e.message);
    }
  }

  const memberIds = new Set((members.data || []).map((m) => m.id));
  const candidates = (volunteers.data || []).filter((v) => !memberIds.has(v.id));

  return (
    <section className="card">
      <h2>Volunteers in this program</h2>
      <ErrorBanner message={error || members.error} onClose={() => setError("")} />
      {!members.data ? (
        <Loading />
      ) : (
        <>
          <div className="row" style={{ marginBottom: "0.8rem" }}>
            <select value={choice} onChange={(e) => setChoice(e.target.value)} aria-label="Volunteer to add">
              <option value="">Choose a volunteer to add&hellip;</option>
              {candidates.map((v) => <option key={v.id} value={v.id}>{v.name} ({v.email})</option>)}
            </select>
            <button
              className="primary"
              disabled={!choice}
              onClick={() =>
                run(async () => {
                  await api(`/programs/${programId}/members`, { method: "POST", body: { user_id: Number(choice) } });
                  setChoice("");
                })
              }
            >
              Add to program
            </button>
          </div>
          {members.data.length === 0 ? (
            <p className="muted">No volunteers yet. Volunteers cannot see this program until you add them.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <tbody>
                  {members.data.map((m) => (
                    <tr key={m.id}>
                      <td>{m.name}</td>
                      <td className="muted">{m.email}</td>
                      <td>
                        <button
                          className="danger"
                          onClick={() => {
                            if (confirm(`Remove ${m.name}? Their upcoming signups in this program will be cancelled.`)) {
                              run(() => api(`/programs/${programId}/members/${m.id}`, { method: "DELETE" }));
                            }
                          }}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
