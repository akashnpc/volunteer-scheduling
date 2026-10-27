export const STATES = {
  open: { label: "Open", color: "#dc2626" },
  partially_filled: { label: "Partially Filled", color: "#d97706" },
  filled: { label: "Filled", color: "#16a34a" },
  closed: { label: "Closed", color: "#6b7280" },
};

// "2026-11-10" -> Date at local midnight (new Date("2026-11-10") would be UTC and can shift a day)
function parseDate(value) {
  const [y, m, d] = value.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function formatDate(value) {
  return parseDate(value).toLocaleDateString("en-GB", {
    weekday: "short", day: "numeric", month: "short", year: "numeric",
  });
}

export function formatShortDate(value) {
  return parseDate(value).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

export function formatDateTime(value) {
  const date = formatShortDate(value);
  return `${date}, ${value.slice(11, 16)}`;
}

/** "09:00-12:00" from the ISO start/end strings the API returns. */
export function formatRange(shift) {
  return `${shift.starts_at.slice(11, 16)}–${shift.ends_at.slice(11, 16)}`;
}

export function formatDuration(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return [h ? `${h}h` : "", m ? `${m}m` : ""].filter(Boolean).join(" ");
}

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
