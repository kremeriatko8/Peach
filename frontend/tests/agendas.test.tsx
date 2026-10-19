import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AgendaDialog } from "@/components/agenda-dialog";
import { agendaApi, type ParseResult, type SavedAgenda } from "@/lib/agendas";
import { ApiError } from "@/lib/api";
import { makeMeeting, renderWithQuery } from "./utils";

const result: ParseResult = {
  agenda: {
    title: null,
    starts_at: null,
    duration_minutes: null,
    items: [{ topic: "Pricing", owner: "Олена", minutes: 15 }],
    action_items: [],
    language: "uk",
  },
  model: "amazon.nova-lite-v1:0",
  prompt_version: "agenda-v1",
  input_tokens: 100,
  output_tokens: 50,
  latency_ms: 1500,
  estimated_cost_usd: 0.000018,
};
const saved: SavedAgenda = {
  id: "a",
  meeting_id: makeMeeting().id,
  items: [],
  action_items: [],
  language: "uk",
  ai_suggestion: null,
  created_at: "",
  updated_at: "",
};
async function open() {
  vi.spyOn(agendaApi, "get").mockResolvedValue(null);
  const put = vi.spyOn(agendaApi, "put").mockResolvedValue(saved);
  const close = vi.fn();
  renderWithQuery(<AgendaDialog meeting={makeMeeting()} onClose={close} />);
  await screen.findByRole("button", { name: "Add agenda item" });
  return { put, close };
}
async function paste() {
  fireEvent.change(screen.getByLabelText("Paste an agenda"), {
    target: { value: "Pricing sync" },
  });
  await userEvent.click(screen.getByRole("button", { name: "Parse" }));
}

describe("Agendas", () => {
  it("saves a manual agenda without calling the parser", async () => {
    const parser = vi.spyOn(agendaApi, "parse");
    const { put, close } = await open();
    await userEvent.click(
      screen.getByRole("button", { name: "Add agenda item" }),
    );
    fireEvent.change(screen.getByLabelText("Item 1 topic"), {
      target: { value: "Manual review" },
    });
    await userEvent.click(screen.getByRole("button", { name: "Save agenda" }));
    await waitFor(() => expect(close).toHaveBeenCalled());
    expect(put).toHaveBeenCalledWith(
      makeMeeting().id,
      expect.objectContaining({
        items: [{ topic: "Manual review", owner: null, minutes: null }],
        ai_suggestion: null,
      }),
      expect.objectContaining({ accessToken: "test-access" }),
    );
    expect(parser).not.toHaveBeenCalled();
  });
  it("prefills editable fields and preserves the original when corrected", async () => {
    vi.spyOn(agendaApi, "parse").mockResolvedValue(structuredClone(result));
    const { put } = await open();
    await paste();
    expect(await screen.findByDisplayValue("Pricing")).toBeInTheDocument();
    expect(screen.getAllByText("AI suggested")).toHaveLength(4);
    fireEvent.change(screen.getByLabelText("Item 1 topic"), {
      target: { value: "Corrected" },
    });
    expect(screen.getAllByText("AI suggested")).toHaveLength(3);
    expect(screen.getByLabelText("starts_at")).toHaveValue("");
    await userEvent.click(screen.getByRole("button", { name: "Save agenda" }));
    await waitFor(() => expect(put).toHaveBeenCalled());
    const payload = put.mock.calls[0][1];
    expect(payload.items[0].topic).toBe("Corrected");
    expect(payload.ai_suggestion?.agenda.items[0].topic).toBe("Pricing");
    expect(payload.ai_suggestion?.model).toBe("amazon.nova-lite-v1:0");
    expect(payload.ai_suggestion?.prompt_version).toBe("agenda-v1");
    expect(payload.meeting).toBeUndefined();
  });
  it("cancels and discards a late parser response", async () => {
    let resolve!: (value: ParseResult) => void;
    const parser = vi.spyOn(agendaApi, "parse").mockImplementation(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    );
    await open();
    await paste();
    expect(screen.getByText("Parsing…")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(parser.mock.calls[0][2].aborted).toBe(true);
    await act(async () => {
      resolve(structuredClone(result));
    });
    expect(screen.queryByDisplayValue("Pricing")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add agenda item" }),
    ).toBeEnabled();
  });
  it("shows parser failure and keeps manual entry available", async () => {
    vi.spyOn(agendaApi, "parse").mockRejectedValue(
      new ApiError(429, "Too many requests"),
    );
    await open();
    await paste();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Too many requests",
    );
    expect(
      screen.getByRole("button", { name: "Add agenda item" }),
    ).toBeEnabled();
  });
  it("prevents oversized text from reaching the parser", async () => {
    const parser = vi.spyOn(agendaApi, "parse");
    await open();
    fireEvent.change(screen.getByLabelText("Paste an agenda"), {
      target: { value: "x".repeat(10001) },
    });
    expect(screen.getByRole("button", { name: "Parse" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("10,000");
    expect(parser).not.toHaveBeenCalled();
  });
  it("retains stored provenance on a later manual edit", async () => {
    vi.spyOn(agendaApi, "get").mockResolvedValue({
      ...saved,
      items: result.agenda.items,
      ai_suggestion: result,
    });
    const put = vi.spyOn(agendaApi, "put").mockResolvedValue(saved);
    renderWithQuery(<AgendaDialog meeting={makeMeeting()} onClose={vi.fn()} />);
    await screen.findByDisplayValue("Pricing");
    fireEvent.change(screen.getByLabelText("Item 1 topic"), {
      target: { value: "Later edit" },
    });
    await userEvent.click(screen.getByRole("button", { name: "Save agenda" }));
    await waitFor(() => expect(put).toHaveBeenCalled());
    expect(put.mock.calls[0][1].ai_suggestion?.agenda.items[0].topic).toBe(
      "Pricing",
    );
  });
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("Parser HTTP client", () => {
  it("sends access JWT and browser date/timezone to the separate parser", async () => {
    vi.stubEnv("NEXT_PUBLIC_PARSER_URL", "https://parser.example/");
    const fetch = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => result });
    vi.stubGlobal("fetch", fetch);
    const controller = new AbortController();
    await agendaApi.parse("Pricing", "access-jwt", controller.signal);
    expect(fetch.mock.calls[0][0]).toBe("https://parser.example/");
    const init = fetch.mock.calls[0][1];
    expect(init.headers.Authorization).toBe("Bearer access-jwt");
    const body = JSON.parse(init.body);
    expect(body.today).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(body.tz).toBe(Intl.DateTimeFormat().resolvedOptions().timeZone);
    expect(body.text).toBe("Pricing");
  });
  it.each([401, 413, 422, 429, 503])(
    "maps HTTP %s to a usable error",
    async (status) => {
      vi.stubEnv("NEXT_PUBLIC_PARSER_URL", "https://parser.example/");
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status }));
      await expect(
        agendaApi.parse("Pricing", "token", new AbortController().signal),
      ).rejects.toMatchObject({ status });
    },
  );
  it("reports connection errors and missing parser configuration", async () => {
    vi.stubEnv("NEXT_PUBLIC_PARSER_URL", "");
    await expect(
      agendaApi.parse("Pricing", "token", new AbortController().signal),
    ).rejects.toMatchObject({ status: 503 });
    vi.stubEnv("NEXT_PUBLIC_PARSER_URL", "https://parser.example/");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network")));
    await expect(
      agendaApi.parse("Pricing", "token", new AbortController().signal),
    ).rejects.toMatchObject({ status: 0 });
  });
});
