"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  Clock3,
  Pencil,
  Plus,
  Trash2,
  Users,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AgendaDialog } from "@/components/agenda-dialog";
import { MeetingFormDialog } from "@/components/meeting-form-dialog";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { Meeting } from "@/lib/api";
import { formatMeetingStart } from "@/lib/meeting-time";
import { MEETINGS_PAGE_SIZE, useMeetingApi, useMeetings } from "@/lib/meetings";

export function Meetings() {
  const [page, setPage] = useState(0);
  const [agendaMeeting, setAgendaMeeting] = useState<Meeting | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Meeting | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Meeting | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const api = useMeetingApi();
  const queryClient = useQueryClient();
  const { data, isPending, isError, error, refetch } = useMeetings(page);
  const remove = useMutation({
    mutationFn: (meeting: Meeting) => api.deleteMeeting(meeting.id),
    onSuccess: async () => {
      if (api.session?.signal.aborted) return;
      if (data?.meetings.length === 1 && page > 0) setPage(page - 1);
      await queryClient.invalidateQueries({ queryKey: api.queryKey });
      if (api.session?.signal.aborted) return;
      toast.success("Meeting deleted");
      setPendingDelete(null);
    },
    onError: (err: Error) => {
      if (!api.session?.signal.aborted) setDeleteError(err.message);
    },
  });

  function create() {
    setEditing(null);
    setOpen(true);
  }

  return (
    <div className="grid gap-8">
      {agendaMeeting && (
        <AgendaDialog
          key={agendaMeeting.id}
          meeting={agendaMeeting}
          onClose={() => setAgendaMeeting(null)}
        />
      )}
      <PageHeader
        icon="🗓️"
        title="Meetings"
        description="Your conversations, with a little more clarity. Times shown in Europe/Kyiv."
        action={
          <Button size="lg" onClick={create}>
            <Plus data-icon="inline-start" className="size-4" />
            New meeting
          </Button>
        }
      />
      {isPending && (
        <div role="status" aria-label="Loading meetings" className="grid gap-3">
          {[0, 1, 2].map((value) => (
            <Skeleton key={value} className="h-28 w-full rounded-xl" />
          ))}
          <span className="sr-only">Loading meetings…</span>
        </div>
      )}
      {isError && (
        <Alert variant="destructive">
          <AlertTitle>Could not load meetings</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-4">
            <span>{error.message}</span>
            <Button size="sm" variant="outline" onClick={() => void refetch()}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      )}
      {!isError && data && (
        <section aria-label="Meeting list" className="grid gap-3">
          <div className="flex items-center justify-between gap-4 text-sm text-muted-foreground">
            <p>
              {data.total} meeting{data.total === 1 ? "" : "s"}
            </p>
            <p>Latest start time first</p>
          </div>
          {data.meetings.length === 0 ? (
            <div className="notion-surface grid justify-items-center gap-3 px-6 py-16 text-center">
              <span className="rounded-xl bg-tint-peach p-3 text-primary">
                <CalendarDays aria-hidden className="size-6" />
              </span>
              <h2 className="text-lg font-semibold">
                {page === 0
                  ? "Room for your next conversation"
                  : "No meetings on this page"}
              </h2>
              <p className="max-w-sm text-sm leading-relaxed text-muted-foreground">
                Record a meeting, its duration, and who took part. Your meetings
                stay private to your account.
              </p>
              <Button variant="outline" onClick={create}>
                Add a meeting
              </Button>
            </div>
          ) : (
            <ul className="grid gap-3">
              {data.meetings.map((meeting) => (
                <li key={meeting.id} className="notion-surface p-4 sm:p-5">
                  <div className="flex items-start gap-3 sm:gap-5">
                    <span className="hidden rounded-lg bg-tint-peach p-2.5 text-primary sm:block">
                      <CalendarDays aria-hidden className="size-5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <h2 className="text-base font-semibold break-words">
                        {meeting.title}
                      </h2>
                      <time
                        dateTime={meeting.starts_at}
                        className="mt-1 block text-sm text-muted-foreground"
                      >
                        {formatMeetingStart(meeting.starts_at)}
                      </time>
                      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-muted-foreground">
                        <span className="inline-flex items-center gap-1.5">
                          <Clock3 aria-hidden className="size-3.5" />
                          {meeting.duration_minutes} min
                        </span>
                        <span className="inline-flex items-center gap-1.5">
                          <Users aria-hidden className="size-3.5" />
                          {meeting.participant_count} participant
                          {meeting.participant_count === 1 ? "" : "s"}
                        </span>
                      </div>
                      {meeting.notes && (
                        <p className="mt-3 text-sm leading-relaxed whitespace-pre-wrap break-words text-muted-foreground">
                          {meeting.notes}
                        </p>
                      )}
                    </div>
                    <div className="flex shrink-0 flex-col gap-1 sm:flex-row">
                      <Button
                        variant="outline"
                        onClick={() => setAgendaMeeting(meeting)}
                        aria-label={`Agenda for ${meeting.title}`}
                      >
                        Agenda
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label={`Edit ${meeting.title}`}
                        onClick={() => {
                          setEditing(meeting);
                          setOpen(true);
                        }}
                      >
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="text-muted-foreground hover:text-destructive"
                        aria-label={`Delete ${meeting.title}`}
                        onClick={() => {
                          setPendingDelete(meeting);
                          setDeleteError(null);
                        }}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {(page > 0 || data.total > MEETINGS_PAGE_SIZE) && (
            <nav
              aria-label="Meetings pagination"
              className="mt-3 flex items-center justify-between gap-4"
            >
              <Button
                variant="outline"
                disabled={page === 0}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {page + 1}
              </span>
              <Button
                variant="outline"
                disabled={(page + 1) * MEETINGS_PAGE_SIZE >= data.total}
                onClick={() => setPage(page + 1)}
              >
                Next
              </Button>
            </nav>
          )}
        </section>
      )}
      <MeetingFormDialog open={open} onOpenChange={setOpen} meeting={editing} />
      <AlertDialog
        open={pendingDelete !== null}
        onOpenChange={(value) => {
          if (!value && !remove.isPending) setPendingDelete(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this meeting?</AlertDialogTitle>
            <AlertDialogDescription>
              &quot;{pendingDelete?.title}&quot; will be removed permanently.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {deleteError && (
            <p role="alert" className="text-sm text-destructive">
              {deleteError}
            </p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={remove.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={remove.isPending}
              onClick={(event) => {
                event.preventDefault();
                setDeleteError(null);
                if (pendingDelete) remove.mutate(pendingDelete);
              }}
            >
              {remove.isPending ? "Deleting…" : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
