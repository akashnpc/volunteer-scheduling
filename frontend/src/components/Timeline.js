"use client";
import { STATES, formatDateTime } from "@/lib/format";

function describe(e) {
  const label = (s) => STATES[s]?.label || s;
  switch (e.event_type) {
    case "created":
      return `Shift created by ${e.actor_name}. ${e.message}`;
    case "edited":
      return `Edited by ${e.actor_name}: ${e.message}`;
    case "signup":
      return e.volunteer_id === e.actor_id
        ? `${e.volunteer_name} signed up`
        : `${e.volunteer_name} was signed up by ${e.actor_name}`;
    case "cancellation":
      return e.volunteer_id === e.actor_id
        ? `${e.volunteer_name} cancelled their signup`
        : `${e.volunteer_name}'s signup was cancelled by ${e.actor_name}${e.message && !e.message.startsWith("Cancelled by") ? ` (${e.message})` : ""}`;
    case "state_change":
      return `Fill state changed: ${label(e.old_state)} → ${label(e.new_state)}${e.message ? ` (${e.message}, ${e.actor_name})` : ""}`;
    case "note":
      return `Note from ${e.actor_name}: ${e.message}`;
    case "deleted":
      return `${e.message} (${e.actor_name})`;
    default:
      return e.message;
  }
}

export default function Timeline({ events }) {
  if (!events.length) return <p className="muted">No history yet.</p>;
  return (
    <ol className="timeline">
      {events.map((e) => (
        <li key={e.id} className={e.event_type}>
          <time dateTime={e.created_at}>{formatDateTime(e.created_at)}</time>
          <div>{describe(e)}</div>
        </li>
      ))}
    </ol>
  );
}
