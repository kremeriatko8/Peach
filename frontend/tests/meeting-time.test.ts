import { describe, expect, it } from "vitest";
import {
  formatMeetingStart,
  kyivOccurrences,
  toKyivLocal,
} from "@/lib/meeting-time";

describe("Europe/Kyiv meeting time", () => {
  it.each([
    ["2026-01-09T10:30", "2026-01-09T08:30:00.000Z", "UTC+02:00"],
    ["2026-07-09T10:30", "2026-07-09T07:30:00.000Z", "UTC+03:00"],
    ["2026-10-09T10:30:45", "2026-10-09T07:30:45.000Z", "UTC+03:00"],
  ])("converts %s explicitly", (local, instant, offset) => {
    expect(kyivOccurrences(local)).toEqual([{ instant, offset }]);
    expect(toKyivLocal(instant)).toBe(
      local.length === 16 ? `${local}:00` : local,
    );
  });
  it("rejects the spring DST gap instead of silently moving the time", () => {
    expect(kyivOccurrences("2026-03-29T03:30")).toEqual([]);
    expect(kyivOccurrences("2026-03-29T02:59")).toHaveLength(1);
    expect(kyivOccurrences("2026-03-29T04:00")).toHaveLength(1);
  });
  it("returns both fall DST occurrences, in chronological order", () => {
    expect(kyivOccurrences("2026-10-25T03:30")).toEqual([
      { instant: "2026-10-25T00:30:00.000Z", offset: "UTC+03:00" },
      { instant: "2026-10-25T01:30:00.000Z", offset: "UTC+02:00" },
    ]);
  });
  it.each([
    "",
    "invalid",
    "2026-02-30T10:00",
    "2026-10-09T25:00",
    "2026-10-09",
    "2026-10-09T10:00Z",
  ])("rejects invalid wall-clock input %s", (value) => {
    expect(kyivOccurrences(value)).toEqual([]);
  });
  it("displays offsets to distinguish a repeated hour", () => {
    expect(formatMeetingStart("2026-10-25T00:30:00Z")).toContain("03:30");
    expect(formatMeetingStart("2026-10-25T00:30:00Z")).toContain("GMT+3");
    expect(formatMeetingStart("2026-10-25T01:30:00Z")).toContain("GMT+2");
  });
});
