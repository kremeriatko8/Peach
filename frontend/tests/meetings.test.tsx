import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Meetings } from "@/components/meetings";
import { api } from "@/lib/api";
import { makeMeeting, renderWithQuery } from "./utils";

function list(meetings = [makeMeeting()], total = meetings.length) {
  return vi.spyOn(api, "listMeetings").mockResolvedValue({ meetings, total });
}
async function openNew() {
  list([]);
  renderWithQuery(<Meetings />);
  await userEvent.click(screen.getByRole("button", { name: "New meeting" }));
}
function fill(local = "2026-10-09T10:30") {
  fireEvent.change(screen.getByLabelText("Title"), {
    target: { value: "Team sync" },
  });
  fireEvent.change(screen.getByLabelText("Start date and time (Kyiv)"), {
    target: { value: local },
  });
}

describe("Meetings", () => {
  it("shows loading, a private list and explicit Kyiv times", async () => {
    list();
    renderWithQuery(<Meetings />);
    expect(
      screen.getByRole("status", { name: "Loading meetings" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Design review")).toBeInTheDocument();
    expect(screen.getByText(/10:30/)).toHaveAttribute(
      "dateTime",
      makeMeeting().starts_at,
    );
    expect(screen.getByText("45 min")).toBeInTheDocument();
    expect(screen.getByText("3 participants")).toBeInTheDocument();
    expect(screen.getByText("Review the agenda")).toBeInTheDocument();
  });
  it("creates a validated meeting with UTC time and current access token", async () => {
    const create = vi
      .spyOn(api, "createMeeting")
      .mockResolvedValue(makeMeeting());
    await openNew();
    fill();
    await userEvent.click(
      screen.getByRole("button", { name: "Create meeting" }),
    );
    await waitFor(() =>
      expect(create).toHaveBeenCalledWith(
        {
          title: "Team sync",
          starts_at: "2026-10-09T07:30:00.000Z",
          duration_minutes: 30,
          participant_count: 1,
          notes: null,
        },
        expect.objectContaining({ accessToken: "test-access" }),
      ),
    );
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
  });
  it("rejects blank titles and invalid numeric fields before sending", async () => {
    const create = vi.spyOn(api, "createMeeting");
    await openNew();
    fill();
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "   " },
    });
    fireEvent.change(screen.getByLabelText("Duration (minutes)"), {
      target: { value: "0" },
    });
    fireEvent.change(screen.getByLabelText("Participants"), {
      target: { value: "1.5" },
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Create meeting" }),
    );
    expect(await screen.findByText("Title is required")).toBeInTheDocument();
    expect(screen.getByLabelText("Duration (minutes)")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.getByLabelText("Participants")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(create).not.toHaveBeenCalled();
  });
  it("rejects a nonexistent spring time", async () => {
    const create = vi.spyOn(api, "createMeeting");
    await openNew();
    fill("2026-03-29T03:30");
    await userEvent.click(
      screen.getByRole("button", { name: "Create meeting" }),
    );
    expect(
      await screen.findByText(/This time does not exist in Kyiv/),
    ).toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
  });
  it("requires an explicit choice for a repeated fall time", async () => {
    const create = vi
      .spyOn(api, "createMeeting")
      .mockResolvedValue(makeMeeting());
    await openNew();
    fill("2026-10-25T03:30");
    await userEvent.click(
      screen.getByRole("button", { name: "Create meeting" }),
    );
    expect(
      await screen.findByText(/Choose the earlier or later occurrence/),
    ).toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("radio", { name: "Later (UTC+02:00)" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Create meeting" }),
    );
    await waitFor(() =>
      expect(create).toHaveBeenCalledWith(
        expect.objectContaining({ starts_at: "2026-10-25T01:30:00.000Z" }),
        expect.anything(),
      ),
    );
  });
  it("edits a meeting without losing its chosen DST occurrence or precision", async () => {
    const meeting = makeMeeting({ starts_at: "2026-10-25T01:30:00.123Z" });
    list([meeting]);
    const update = vi.spyOn(api, "updateMeeting").mockResolvedValue(meeting);
    renderWithQuery(<Meetings />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Edit Design review" }),
    );
    expect(
      screen.getByRole("radio", { name: "Later (UTC+02:00)" }),
    ).toBeChecked();
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "Revised" },
    });
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() =>
      expect(update).toHaveBeenCalledWith(
        meeting.id,
        expect.objectContaining({
          title: "Revised",
          starts_at: meeting.starts_at,
        }),
        expect.anything(),
      ),
    );
  });
  it("keeps a failed save open with an error and permits retry", async () => {
    const create = vi
      .spyOn(api, "createMeeting")
      .mockRejectedValueOnce(new Error("Save unavailable"))
      .mockResolvedValue(makeMeeting());
    await openNew();
    fill();
    await userEvent.click(
      screen.getByRole("button", { name: "Create meeting" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Save unavailable",
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Create meeting" }),
    );
    await waitFor(() => expect(create).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
  });
  it("requires deletion confirmation, retains errors and retries", async () => {
    const listing = list();
    const remove = vi
      .spyOn(api, "deleteMeeting")
      .mockRejectedValueOnce(new Error("Delete unavailable"))
      .mockResolvedValue(undefined);
    renderWithQuery(<Meetings />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Delete Design review" }),
    );
    expect(remove).not.toHaveBeenCalled();
    const dialog = screen.getByRole("alertdialog");
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Delete" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Delete unavailable",
    );
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    listing.mockResolvedValue({ meetings: [], total: 0 });
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Delete" }),
    );
    expect(
      await screen.findByText("Room for your next conversation"),
    ).toBeInTheDocument();
    expect(remove).toHaveBeenCalledTimes(2);
  });
  it("can cancel deletion without a request", async () => {
    list();
    const remove = vi.spyOn(api, "deleteMeeting");
    renderWithQuery(<Meetings />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Delete Design review" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(remove).not.toHaveBeenCalled();
  });
  it("provides a retry action when listing fails", async () => {
    vi.spyOn(api, "listMeetings").mockRejectedValue(new Error("Offline"));
    renderWithQuery(<Meetings />);
    expect(
      await screen.findByText("Could not load meetings", {}, { timeout: 3000 }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
  it("paginates without displaying stale previous-page records", async () => {
    const listing = list([makeMeeting()], 21);
    renderWithQuery(<Meetings />);
    await screen.findByText("Design review");
    listing.mockResolvedValue({
      meetings: [makeMeeting({ title: "Older meeting" })],
      total: 21,
    });
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByText("Older meeting");
    expect(screen.queryByText("Design review")).not.toBeInTheDocument();
    expect(listing).toHaveBeenLastCalledWith(
      { limit: 20, offset: 20 },
      expect.anything(),
    );
  });
});

describe("Paste an Agenda entry point", () => {
  it("opens the existing agenda editor for an explicitly selected meeting", async () => {
    const { agendaApi } = await import("@/lib/agendas");
    list();
    const get = vi.spyOn(agendaApi, "get").mockResolvedValue(null);
    const create = vi.spyOn(api, "createMeeting");
    renderWithQuery(<Meetings />);
    await userEvent.click(
      screen.getByRole("button", { name: "Paste an Agenda" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Design review" }),
    );
    expect(await screen.findByLabelText("Paste an agenda")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Parse" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add agenda item" }),
    ).toBeEnabled();
    expect(get).toHaveBeenCalledWith(makeMeeting().id, expect.anything());
    expect(create).not.toHaveBeenCalled();
  });

  it("guides an empty account through explicit meeting creation into the same agenda editor", async () => {
    const { agendaApi } = await import("@/lib/agendas");
    list([]);
    const create = vi
      .spyOn(api, "createMeeting")
      .mockResolvedValue(makeMeeting());
    vi.spyOn(agendaApi, "get").mockResolvedValue(null);
    const parse = vi.spyOn(agendaApi, "parse");
    renderWithQuery(<Meetings />);
    await userEvent.click(
      screen.getByRole("button", { name: "Paste an Agenda" }),
    );
    expect(
      await screen.findByText(
        "No meetings on this page. Create a meeting to add its agenda.",
      ),
    ).toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Create meeting and continue" }),
    );
    expect(
      screen.getByText(/Create the meeting first, then paste/),
    ).toBeInTheDocument();
    fill();
    await userEvent.click(
      screen.getByRole("button", { name: "Create meeting and open agenda" }),
    );
    expect(await screen.findByLabelText("Paste an agenda")).toBeInTheDocument();
    expect(create).toHaveBeenCalledTimes(1);
    expect(parse).not.toHaveBeenCalled();
  });

  it("does not alter ordinary New meeting after canceling the agenda creation flow", async () => {
    list([]);
    renderWithQuery(<Meetings />);
    await userEvent.click(
      screen.getByRole("button", { name: "Paste an Agenda" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Create meeting and continue" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await userEvent.click(screen.getByRole("button", { name: "New meeting" }));
    expect(
      screen.getByRole("button", { name: "Create meeting" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Create meeting and open agenda" }),
    ).not.toBeInTheDocument();
  });

  it("keeps the existing manual editor usable after a disabled parser response", async () => {
    const { agendaApi } = await import("@/lib/agendas");
    const { ApiError } = await import("@/lib/api");
    list();
    vi.spyOn(agendaApi, "get").mockResolvedValue(null);
    vi.spyOn(agendaApi, "parse").mockRejectedValue(
      new ApiError(503, "Parsing unavailable. Enter your agenda manually."),
    );
    renderWithQuery(<Meetings />);
    await userEvent.click(
      screen.getByRole("button", { name: "Paste an Agenda" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: "Design review" }),
    );
    await screen.findByLabelText("Paste an agenda");
    fireEvent.change(screen.getByLabelText("Paste an agenda"), {
      target: { value: "Review work" },
    });
    await userEvent.click(screen.getByRole("button", { name: "Parse" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("manually");
    await userEvent.click(
      screen.getByRole("button", { name: "Add agenda item" }),
    );
    expect(screen.getByLabelText("Item 1 topic")).toBeEnabled();
  });
});
