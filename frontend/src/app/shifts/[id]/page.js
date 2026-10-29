"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { useLoad } from "@/lib/hooks";
import { formatDate, formatDuration, formatRange } from "@/lib/format";
import CoordinatorActions from "@/components/shift/CoordinatorActions";
import HistoryCard from "@/components/shift/HistoryCard";
import SignupsCard from "@/components/shift/SignupsCard";
import { ErrorBanner, Loading, PageHeader, StateBadge } from "@/components/ui";

export default function ShiftPage() {
  const { id } = useParams();
  const router = useRouter();
  const auth = useRequireAuth();
  const [error, setError] = useState("");

  const shift = useLoad(() => (auth.allowed ? api(`/shifts/${id}`) : Promise.resolve(null)), [auth.allowed, id]);
  const timeline = useLoad(() => (auth.allowed ? api(`/shifts/${id}/timeline`) : Promise.resolve(null)), [auth.allowed, id]);
  const programId = shift.data?.program_id;
  const members = useLoad(
    () => (auth.isCoordinator && programId ? api(`/programs/${programId}/members`) : Promise.resolve([])),
    [auth.isCoordinator, programId],
  );

  if (!auth.allowed) return <Loading />;
  const s = shift.data;
  if (!s) return shift.error ? <ErrorBanner message={shift.error} /> : <Loading />;

  // Run an API call, show its error in the banner, then reload what the page shows.
  async function run(action) {
    setError("");
    try {
      await action();
      shift.reload();
      timeline.reload();
    } catch (e) {
      setError(e.message);
    }
  }

  const deleteShift = () =>
    api(`/shifts/${id}`, { method: "DELETE" })
      .then(() => router.replace(`/programs/${s.program_id}`))
      .catch((e) => setError(e.message));

  return (
    <>
      <PageHeader
        title={`${s.program_name}: ${formatDate(s.date)}`}
        subtitle={`${formatRange(s)} (${formatDuration(s.duration_minutes)}) at ${s.location}`}
      >
        <StateBadge state={s.state} />
        <Link className="button" href={`/programs/${s.program_id}`}>Back to program</Link>
      </PageHeader>
      <ErrorBanner message={error || shift.error} onClose={() => setError("")} />

      <SignupsCard shift={s} isCoordinator={auth.isCoordinator} members={members.data || []} run={run} />
      {auth.isCoordinator && <CoordinatorActions shift={s} run={run} onDelete={deleteShift} />}
      <HistoryCard shiftId={id} isCoordinator={auth.isCoordinator} timeline={timeline} run={run} />
    </>
  );
}
