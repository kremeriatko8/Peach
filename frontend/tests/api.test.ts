import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "@/lib/api";

function mockFetch(body: unknown, init: { status?: number } = {}) {
  const status = init.status ?? 200;
  return vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response);
}

afterEach(() => vi.restoreAllMocks());

describe("api", () => {
  it("parses a list response", async () => {
    mockFetch({ items: [], total: 0 });
    await expect(
      api.listItems({}, { accessToken: "access-token" }),
    ).resolves.toEqual({ items: [], total: 0 });
  });

  it("passes pagination through as query parameters", async () => {
    const spy = mockFetch({ items: [], total: 0 });
    await api.listItems(
      { limit: 5, offset: 10 },
      { accessToken: "access-token" },
    );
    expect(spy.mock.calls[0][0]).toContain("/api/v1/items?limit=5&offset=10");
  });

  it("raises ApiError carrying the detail from the backend", async () => {
    mockFetch({ detail: "Item not found" }, { status: 404 });
    await expect(
      api.listItems({}, { accessToken: "access-token" }),
    ).rejects.toMatchObject({
      status: 404,
      message: "Item not found",
    });
  });

  it("raises ApiError when the network is unreachable", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
      throw new TypeError("failed");
    });
    await expect(
      api.listItems({}, { accessToken: "access-token" }),
    ).rejects.toBeInstanceOf(ApiError);
  });
});

describe("meeting API", () => {
  it("sends only the access token for CRUD and preserves request bodies", async () => {
    const meeting = {
      id: "22222222-2222-4222-8222-222222222222",
      title: "Sync",
      starts_at: "2026-10-09T07:00:00Z",
      duration_minutes: 30,
      participant_count: 1,
      notes: null,
      created_at: "2026-10-09T00:00:00Z",
      updated_at: "2026-10-09T00:00:00Z",
    };
    const spy = mockFetch({ meetings: [meeting], total: 1 });
    const auth = {
      accessToken: "access-token",
      signal: new AbortController().signal,
    };
    await api.listMeetings({ limit: 20, offset: 40 }, auth);
    expect(spy.mock.calls[0][0]).toContain(
      "/api/v1/meetings?limit=20&offset=40",
    );
    spy.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => meeting,
    } as Response);
    await api.getMeeting(meeting.id, auth);
    const payload = {
      title: "Sync",
      starts_at: meeting.starts_at,
      duration_minutes: 30,
      participant_count: 1,
      notes: null,
    };
    await api.createMeeting(payload, auth);
    await api.updateMeeting(meeting.id, { notes: null }, auth);
    spy.mockResolvedValue({ ok: true, status: 204 } as Response);
    await expect(api.deleteMeeting(meeting.id, auth)).resolves.toBeUndefined();
    for (const [, init] of spy.mock.calls) {
      expect(init?.headers).toMatchObject({
        Authorization: "Bearer access-token",
      });
      expect(init?.signal).toBe(auth.signal);
    }
    expect(JSON.parse(spy.mock.calls[2][1]?.body as string)).toEqual(payload);
    expect(JSON.parse(spy.mock.calls[3][1]?.body as string)).toEqual({
      notes: null,
    });
  });
  it("rejects missing tokens before making a request", async () => {
    const spy = mockFetch({ meetings: [], total: 0 });
    expect(() => api.listMeetings({}, { accessToken: "" })).toThrow(ApiError);
    expect(spy).not.toHaveBeenCalled();
  });
});
