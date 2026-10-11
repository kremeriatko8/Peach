"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { meetingInputSchema, type Meeting } from "@/lib/api";
import { kyivOccurrences, toKyivLocal } from "@/lib/meeting-time";
import { useMeetingApi } from "@/lib/meetings";

const formSchema = meetingInputSchema
  .omit({ starts_at: true, notes: true })
  .extend({
    local_start: z
      .string()
      .min(1, "Start time is required")
      .refine(
        (value) => kyivOccurrences(value).length > 0,
        "This time does not exist in Kyiv. Choose a valid date and time.",
      ),
    occurrence: z.string(),
    notes: z.string().max(2000, "Notes are too long"),
  });
type FormValues = z.infer<typeof formSchema>;

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  meeting: Meeting | null;
};

export function MeetingFormDialog({ open, onOpenChange, meeting }: Props) {
  const queryClient = useQueryClient();
  const api = useMeetingApi();
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      title: "",
      local_start: "",
      occurrence: "",
      duration_minutes: 30,
      participant_count: 1,
      notes: "",
    },
  });
  useEffect(() => {
    if (!open) return;
    const local = meeting ? toKyivLocal(meeting.starts_at) : "";
    const occurrence = meeting
      ? (kyivOccurrences(local).find(
          (candidate) =>
            candidate.instant.slice(0, 19) ===
            new Date(meeting.starts_at).toISOString().slice(0, 19),
        )?.instant ?? "")
      : "";
    form.reset({
      title: meeting?.title ?? "",
      local_start: local,
      occurrence,
      duration_minutes: meeting?.duration_minutes ?? 30,
      participant_count: meeting?.participant_count ?? 1,
      notes: meeting?.notes ?? "",
    });
  }, [open, meeting, form]);

  const local = useWatch({ control: form.control, name: "local_start" });
  const occurrences = kyivOccurrences(local);
  const chosen = useWatch({ control: form.control, name: "occurrence" });
  const mutation = useMutation({
    mutationFn: (values: FormValues & { starts_at: string }) => {
      const payload = meetingInputSchema.parse({
        title: values.title,
        starts_at: values.starts_at,
        duration_minutes: values.duration_minutes,
        participant_count: values.participant_count,
        notes: values.notes.trim() || null,
      });
      return meeting
        ? api.updateMeeting(meeting.id, payload)
        : api.createMeeting(payload);
    },
    onSuccess: async () => {
      if (api.session?.signal.aborted) return;
      await queryClient.invalidateQueries({ queryKey: api.queryKey });
      if (api.session?.signal.aborted) return;
      toast.success(meeting ? "Meeting updated" : "Meeting created");
      onOpenChange(false);
    },
    onError: (error: Error) => {
      if (!api.session?.signal.aborted)
        form.setError("root", { message: error.message });
    },
  });

  function submit(values: FormValues) {
    const choices = kyivOccurrences(values.local_start);
    const selected =
      choices.length === 1
        ? choices[0]
        : choices.find((value) => value.instant === values.occurrence);
    if (!selected) {
      form.setError("occurrence", {
        message: "Choose the earlier or later occurrence of this time.",
      });
      return;
    }
    // Preserve subsecond precision when an existing start time is left unchanged.
    const starts_at =
      meeting &&
      toKyivLocal(meeting.starts_at) === values.local_start &&
      new Date(meeting.starts_at).toISOString().slice(0, 19) ===
        selected.instant.slice(0, 19)
        ? meeting.starts_at
        : selected.instant;
    form.clearErrors("root");
    mutation.mutate({ ...values, starts_at });
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => !mutation.isPending && onOpenChange(value)}
    >
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{meeting ? "Edit meeting" : "New meeting"}</DialogTitle>
          <DialogDescription>
            Make room for a conversation. All times are in Europe/Kyiv.
          </DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4"
          onSubmit={form.handleSubmit(submit)}
          noValidate
        >
          <Field data-invalid={!!form.formState.errors.title}>
            <FieldLabel htmlFor="meeting-title">Title</FieldLabel>
            <Input
              id="meeting-title"
              autoComplete="off"
              aria-invalid={!!form.formState.errors.title}
              {...form.register("title")}
            />
            <FieldError errors={[form.formState.errors.title]} />
          </Field>
          <Field data-invalid={!!form.formState.errors.local_start}>
            <FieldLabel htmlFor="meeting-start">
              Start date and time (Kyiv)
            </FieldLabel>
            <Input
              id="meeting-start"
              type="datetime-local"
              step="1"
              aria-invalid={!!form.formState.errors.local_start}
              {...form.register("local_start", {
                onChange: () => {
                  form.setValue("occurrence", "");
                  form.clearErrors("occurrence");
                },
              })}
            />
            <FieldError errors={[form.formState.errors.local_start]} />
          </Field>
          {occurrences.length > 1 && (
            <fieldset className="grid gap-2 rounded-lg border border-border bg-muted p-3">
              <legend className="px-1 text-sm font-medium">
                This time occurs twice in Kyiv
              </legend>
              <p className="text-xs text-muted-foreground">
                Clocks move back. Choose which occurrence you mean.
              </p>
              {occurrences.map((occurrence, index) => (
                <label
                  key={occurrence.instant}
                  className="flex items-center gap-2 text-sm"
                >
                  <input
                    type="radio"
                    value={occurrence.instant}
                    checked={chosen === occurrence.instant}
                    {...form.register("occurrence")}
                  />
                  {index === 0 ? "Earlier" : "Later"} ({occurrence.offset})
                </label>
              ))}
              <FieldError errors={[form.formState.errors.occurrence]} />
            </fieldset>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field data-invalid={!!form.formState.errors.duration_minutes}>
              <FieldLabel htmlFor="meeting-duration">
                Duration (minutes)
              </FieldLabel>
              <Input
                id="meeting-duration"
                type="number"
                min="1"
                max="1440"
                step="1"
                aria-invalid={!!form.formState.errors.duration_minutes}
                {...form.register("duration_minutes", { valueAsNumber: true })}
              />
              <FieldError errors={[form.formState.errors.duration_minutes]} />
            </Field>
            <Field data-invalid={!!form.formState.errors.participant_count}>
              <FieldLabel htmlFor="meeting-participants">
                Participants
              </FieldLabel>
              <Input
                id="meeting-participants"
                type="number"
                min="1"
                max="10000"
                step="1"
                aria-invalid={!!form.formState.errors.participant_count}
                {...form.register("participant_count", { valueAsNumber: true })}
              />
              <p className="text-xs text-muted-foreground">Include yourself.</p>
              <FieldError errors={[form.formState.errors.participant_count]} />
            </Field>
          </div>
          <Field data-invalid={!!form.formState.errors.notes}>
            <FieldLabel htmlFor="meeting-notes">
              Notes{" "}
              <span className="font-normal text-muted-foreground">
                (optional)
              </span>
            </FieldLabel>
            <Textarea
              id="meeting-notes"
              rows={3}
              aria-invalid={!!form.formState.errors.notes}
              placeholder="Agenda, location, or a little context…"
              {...form.register("notes")}
            />
            <FieldError errors={[form.formState.errors.notes]} />
          </Field>
          {form.formState.errors.root && (
            <p role="alert" className="text-sm text-destructive">
              {form.formState.errors.root.message}
            </p>
          )}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending
                ? "Saving…"
                : meeting
                  ? "Save changes"
                  : "Create meeting"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
