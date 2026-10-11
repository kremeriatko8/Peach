export const MEETING_TIMEZONE = "Europe/Kyiv";

const wallFormatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: MEETING_TIMEZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

/** A wall-clock value, independent of the browser/server's own timezone. */
export function toKyivLocal(instant: string | Date): string {
  const parts = wallFormatter.formatToParts(new Date(instant));
  const part = (name: string) => parts.find((p) => p.type === name)!.value;
  return `${part("year")}-${part("month")}-${part("day")}T${part("hour")}:${part("minute")}:${part("second")}`;
}

export type KyivOccurrence = { instant: string; offset: string };

/** Round-trip every nearby timezone offset; gaps have 0 matches, folds have 2.
 * No implicit Date(local) conversion or silent DST adjustment is used.
 */
export function kyivOccurrences(local: string): KyivOccurrence[] {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(local)) return [];
  const wall = local.length === 16 ? `${local}:00` : local;
  const naive = new Date(`${wall}Z`).getTime();
  if (
    !Number.isFinite(naive) ||
    new Date(naive).toISOString().slice(0, 19) !== wall
  )
    return [];
  const offsets = new Set<number>();
  for (let hours = -36; hours <= 36; hours += 6) {
    const sample = naive + hours * 3600000;
    offsets.add(
      new Date(`${toKyivLocal(new Date(sample))}Z`).getTime() - sample,
    );
  }
  return [...offsets]
    .map((offset) => ({ offset, value: naive - offset }))
    .filter(({ value }) => toKyivLocal(new Date(value)) === wall)
    .sort((a, b) => a.value - b.value)
    .map(({ offset, value }) => {
      const minutes = Math.abs(offset) / 60000;
      const hh = String(Math.floor(minutes / 60)).padStart(2, "0");
      const mm = String(Math.floor(minutes % 60)).padStart(2, "0");
      return {
        instant: new Date(value).toISOString(),
        offset: `UTC${offset < 0 ? "-" : "+"}${hh}:${mm}`,
      };
    });
}

export function formatMeetingStart(instant: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: MEETING_TIMEZONE,
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "shortOffset",
  }).format(new Date(instant));
}
