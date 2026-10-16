"use client";

import { useContext, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { ItemSessionContext } from "@/components/item-session";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, meetingInputSchema, type Meeting } from "@/lib/api";
import {
  agendaApi,
  parsedAgendaSchema,
  type ParsedAgenda,
  type Suggestion,
  type ParseResult,
} from "@/lib/agendas";

const empty: ParsedAgenda = {
  title: null,
  starts_at: null,
  duration_minutes: null,
  items: [],
  action_items: [],
  language: "und",
};

export function AgendaDialog({
  meeting,
  onClose,
}: {
  meeting: Meeting;
  onClose: () => void;
}) {
  const session = useContext(ItemSessionContext);
  const client = useQueryClient();
  const [draft, setDraft] = useState<ParsedAgenda>(empty);
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [suggested, setSuggested] = useState<Set<string>>(new Set());
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<ParseResult | null>(null);
  const [applyMeeting, setApplyMeeting] = useState(false);
  const request = useRef<AbortController | null>(null);
  const [lifetime] = useState(() => new AbortController());
  const query = useQuery({
    queryKey: ["agendas", session?.sub, meeting.id],
    enabled: !!session,
    queryFn: ({ signal }) =>
      agendaApi.get(meeting.id, {
        accessToken: session!.accessToken,
        signal: AbortSignal.any([signal, session!.signal]),
      }),
    retry: false,
  });
  const [initialized, setInitialized] = useState(false);
  if (query.isSuccess && !initialized) {
    setInitialized(true);
    const data = query.data;
    setDraft(
      data
        ? {
            ...empty,
            items: data.items,
            action_items: data.action_items,
            language: data.language,
          }
        : empty,
    );
    setSuggestion(data?.ai_suggestion ?? null);
  }
  useEffect(() => {
    if (query.error instanceof ApiError && query.error.status === 401)
      session?.unauthorized();
  }, [query.error, session]);
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      queueMicrotask(() => {
        if (!mounted.current) {
          lifetime.abort();
          request.current?.abort();
        }
      });
    };
  }, [lifetime]);
  if (!session) return null;
  const auth = {
    accessToken: session.accessToken,
    signal: AbortSignal.any([session.signal, lifetime.signal]),
  };
  function fail(err: unknown) {
    if (auth.signal.aborted) return;
    if (err instanceof ApiError && err.status === 401) session?.unauthorized();
    setError(
      err instanceof Error ? err.message : "Could not complete the request.",
    );
  }
  function edit(key: string) {
    setSuggested((old) => {
      const next = new Set(old);
      next.delete(key);
      return next;
    });
  }
  function removeMarkers(prefix: string, index: number) {
    setSuggested(
      (old) =>
        new Set(
          [...old].flatMap((key) => {
            const [group, position, field] = key.split(".");
            if (group !== prefix) return [key];
            const current = Number(position);
            if (current === index) return [];
            return [
              `${prefix}.${current > index ? current - 1 : current}.${field}`,
            ];
          }),
        ),
    );
  }
  function marker(key: string) {
    return suggested.has(key) ? (
      <span className="ml-2 text-xs text-primary">AI suggested</span>
    ) : null;
  }
  function close() {
    request.current?.abort();
    lifetime.abort();
    onClose();
  }
  async function parse() {
    const controller = new AbortController();
    request.current?.abort();
    request.current = controller;
    const signal = AbortSignal.any([controller.signal, auth.signal]);
    setBusy(true);
    setError(null);
    try {
      const result = await agendaApi.parse(text, auth.accessToken, signal);
      signal.throwIfAborted();
      setDraft(structuredClone(result.agenda));
      setSuggestion({
        agenda: structuredClone(result.agenda),
        model: result.model,
        prompt_version: result.prompt_version,
      });
      setMetrics(result);
      setApplyMeeting(false);
      setSuggested(
        new Set([
          ...["title", "starts_at", "duration_minutes", "language"].filter(
            (k) => result.agenda[k as keyof ParsedAgenda] !== null,
          ),
          ...result.agenda.items.flatMap((_, i) =>
            ["topic", "owner", "minutes"]
              .filter(
                (k) =>
                  result.agenda.items[i][
                    k as keyof ParsedAgenda["items"][number]
                  ] !== null,
              )
              .map((k) => `items.${i}.${k}`),
          ),
          ...result.agenda.action_items.flatMap((_, i) =>
            ["task", "owner", "due"]
              .filter(
                (k) =>
                  result.agenda.action_items[i][
                    k as keyof ParsedAgenda["action_items"][number]
                  ] !== null,
              )
              .map((k) => `actions.${i}.${k}`),
          ),
        ]),
      );
      if (!result.agenda.items.length && !result.agenda.action_items.length)
        setError("No agenda found. You can enter it manually.");
    } catch (err) {
      if (!signal.aborted) fail(err);
    } finally {
      if (request.current === controller && !auth.signal.aborted)
        setBusy(false);
    }
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const validated = parsedAgendaSchema.parse(draft);
      let changes;
      if (applyMeeting) {
        const result = meetingInputSchema
          .pick({ title: true, starts_at: true, duration_minutes: true })
          .parse({
            title: validated.title,
            starts_at: validated.starts_at,
            duration_minutes: validated.duration_minutes,
          });
        changes = result;
      }
      await agendaApi.put(
        meeting.id,
        {
          items: validated.items,
          action_items: validated.action_items,
          language: validated.language,
          ai_suggestion: suggestion,
          ...(changes ? { meeting: changes } : {}),
        },
        auth,
      );
      auth.signal.throwIfAborted();
      await Promise.all([
        client.invalidateQueries({ queryKey: ["agendas", session!.sub] }),
        client.invalidateQueries({ queryKey: ["meetings", session!.sub] }),
      ]);
      auth.signal.throwIfAborted();
      close();
    } catch (err) {
      fail(
        err instanceof z.ZodError
          ? new Error(err.issues[0]?.message ?? "Check the form")
          : err,
      );
    } finally {
      if (!auth.signal.aborted) setSaving(false);
    }
  }
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) close();
      }}
    >
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Agenda · {meeting.title}</DialogTitle>
          <DialogDescription>
            Enter an agenda manually, or paste notes for suggestions. Review
            before saving.
          </DialogDescription>
        </DialogHeader>
        {query.isPending ? (
          <p role="status">Loading agenda…</p>
        ) : query.isError ? (
          <div role="alert">
            Could not load agenda.{" "}
            <Button onClick={() => void query.refetch()}>Retry</Button>
          </div>
        ) : (
          <>
            <section className="grid gap-3" aria-label="Agenda parser">
              <label htmlFor="paste-agenda">Paste an agenda</label>
              <Textarea
                id="paste-agenda"
                value={text}
                disabled={busy || saving}
                onChange={(e) => setText(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                {text.length}/10,000 characters · Dates interpreted in{" "}
                {Intl.DateTimeFormat().resolvedOptions().timeZone}. Parsing
                sends this text to Amazon Bedrock.
              </p>
              <div className="flex gap-2">
                <Button
                  type="button"
                  disabled={
                    busy || saving || !text.trim() || text.length > 10000
                  }
                  onClick={() => void parse()}
                >
                  Parse
                </Button>
                {busy && (
                  <>
                    <span role="status">Parsing…</span>
                    <Button
                      variant="outline"
                      onClick={() => {
                        request.current?.abort();
                        setBusy(false);
                      }}
                    >
                      Cancel
                    </Button>
                  </>
                )}
              </div>
              {text.length > 10000 && (
                <p role="alert">Use at most 10,000 characters.</p>
              )}
            </section>
            {error && (
              <p role="alert" className="text-destructive">
                {error}
              </p>
            )}
            {metrics && (
              <p className="text-xs text-muted-foreground">
                {metrics.input_tokens} input / {metrics.output_tokens} output
                tokens · {(metrics.latency_ms / 1000).toFixed(2)} s ·{" "}
                {metrics.estimated_cost_usd === null
                  ? "Cost unavailable"
                  : `$${metrics.estimated_cost_usd.toFixed(6)}`}
              </p>
            )}
            <form
              onSubmit={save}
              className="grid gap-4"
              aria-label="Agenda editor"
            >
              <fieldset disabled={busy || saving} className="grid gap-4">
                <p className="text-sm">
                  Missing or ambiguous values remain blank. Names are labels,
                  not account permissions.
                </p>
                {(
                  [
                    "title",
                    "starts_at",
                    "duration_minutes",
                    "language",
                  ] as const
                ).map((key) => (
                  <label key={key}>
                    {
                      {
                        title: "Suggested meeting title",
                        starts_at:
                          "Suggested start (ISO timestamp with offset)",
                        duration_minutes: "Suggested duration (minutes)",
                        language: "Language",
                      }[key]
                    }
                    {marker(key)}
                    <Input
                      aria-label={key}
                      value={draft[key] ?? ""}
                      type={key === "duration_minutes" ? "number" : "text"}
                      onChange={(e) => {
                        edit(key);
                        setDraft({
                          ...draft,
                          [key]:
                            key === "duration_minutes"
                              ? e.target.value
                                ? Number(e.target.value)
                                : null
                              : e.target.value ||
                                (key === "language" ? "" : null),
                        });
                      }}
                    />
                  </label>
                ))}
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={applyMeeting}
                    onChange={(e) => setApplyMeeting(e.target.checked)}
                  />
                  Apply reviewed title, start and duration to this meeting
                </label>
                <p className="text-xs">
                  Leave unchecked to keep the meeting details. Applying requires
                  all three fields and a start with an explicit UTC offset.
                </p>
                <h3>Agenda items</h3>
                {draft.items.map((item, i) => (
                  <div className="grid gap-2 rounded border p-3" key={i}>
                    {(["topic", "owner", "minutes"] as const).map((key) => (
                      <label key={key}>
                        {key}
                        {marker(`items.${i}.${key}`)}
                        <Input
                          aria-label={`Item ${i + 1} ${key}`}
                          type={key === "minutes" ? "number" : "text"}
                          value={item[key] ?? ""}
                          onChange={(e) => {
                            edit(`items.${i}.${key}`);
                            setDraft({
                              ...draft,
                              items: draft.items.map((v, j) =>
                                j === i
                                  ? {
                                      ...v,
                                      [key]:
                                        key === "minutes"
                                          ? e.target.value
                                            ? Number(e.target.value)
                                            : null
                                          : e.target.value ||
                                            (key === "owner" ? null : ""),
                                    }
                                  : v,
                              ),
                            });
                          }}
                        />
                      </label>
                    ))}
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setDraft({
                          ...draft,
                          items: draft.items.filter((_, j) => j !== i),
                        });
                        removeMarkers("items", i);
                      }}
                    >
                      Remove item
                    </Button>
                  </div>
                ))}
                <Button
                  type="button"
                  variant="outline"
                  onClick={() =>
                    setDraft({
                      ...draft,
                      items: [
                        ...draft.items,
                        { topic: "", owner: null, minutes: null },
                      ],
                    })
                  }
                >
                  Add agenda item
                </Button>
                <h3>Action items</h3>
                {draft.action_items.map((item, i) => (
                  <div className="grid gap-2 rounded border p-3" key={i}>
                    {(["task", "owner", "due"] as const).map((key) => (
                      <label key={key}>
                        {key}
                        {marker(`actions.${i}.${key}`)}
                        <Input
                          aria-label={`Action ${i + 1} ${key}`}
                          type={key === "due" ? "date" : "text"}
                          value={item[key] ?? ""}
                          onChange={(e) => {
                            edit(`actions.${i}.${key}`);
                            setDraft({
                              ...draft,
                              action_items: draft.action_items.map((v, j) =>
                                j === i
                                  ? {
                                      ...v,
                                      [key]:
                                        e.target.value ||
                                        (key === "task" ? "" : null),
                                    }
                                  : v,
                              ),
                            });
                          }}
                        />
                      </label>
                    ))}
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setDraft({
                          ...draft,
                          action_items: draft.action_items.filter(
                            (_, j) => j !== i,
                          ),
                        });
                        removeMarkers("actions", i);
                      }}
                    >
                      Remove action
                    </Button>
                  </div>
                ))}
                <Button
                  type="button"
                  variant="outline"
                  onClick={() =>
                    setDraft({
                      ...draft,
                      action_items: [
                        ...draft.action_items,
                        { task: "", owner: null, due: null },
                      ],
                    })
                  }
                >
                  Add action item
                </Button>
                <Button type="submit">
                  {saving ? "Saving…" : "Save agenda"}
                </Button>
              </fieldset>
            </form>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
