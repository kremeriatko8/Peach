"use client";

import { z } from "zod";
import { api, ApiError } from "@/lib/api";

export const agendaItemSchema = z.object({
  topic: z
    .string()
    .min(1)
    .max(2000)
    .refine((v) => !!v.trim(), "Topic is required"),
  owner: z.string().max(200).nullable(),
  minutes: z.number().int().min(1).max(480).nullable(),
});
export const actionItemSchema = z.object({
  task: z
    .string()
    .min(1)
    .max(2000)
    .refine((v) => !!v.trim(), "Task is required"),
  owner: z.string().max(200).nullable(),
  due: z.iso.date().nullable(),
});
export const parsedAgendaSchema = z.object({
  title: z.string().nullable(),
  starts_at: z.string().nullable(),
  duration_minutes: z.number().int().min(1).max(600).nullable(),
  items: z.array(agendaItemSchema).max(100),
  action_items: z.array(actionItemSchema).max(100),
  language: z.string().min(1).max(64),
});
export const suggestionSchema = z.object({
  agenda: parsedAgendaSchema,
  model: z.string(),
  prompt_version: z.string(),
});
export const savedAgendaSchema = z.object({
  id: z.string(),
  meeting_id: z.string(),
  items: z.array(agendaItemSchema),
  action_items: z.array(actionItemSchema),
  language: z.string(),
  ai_suggestion: suggestionSchema.nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
export const parseResultSchema = suggestionSchema.extend({
  input_tokens: z.number(),
  output_tokens: z.number(),
  latency_ms: z.number(),
  estimated_cost_usd: z.number().nullable(),
});
export type ParsedAgenda = z.infer<typeof parsedAgendaSchema>;
export type Suggestion = z.infer<typeof suggestionSchema>;
export type SavedAgenda = z.infer<typeof savedAgendaSchema>;
export type ParseResult = z.infer<typeof parseResultSchema>;
export type AgendaSave = Pick<
  SavedAgenda,
  "items" | "action_items" | "language" | "ai_suggestion"
> & {
  meeting?: { title: string; starts_at: string; duration_minutes: number };
};
export const agendaApi = {
  get: (id: string, auth: { accessToken: string; signal?: AbortSignal }) =>
    api.request(
      `/api/v1/meetings/${id}/agenda`,
      savedAgendaSchema.nullable(),
      undefined,
      auth,
    ),
  put: (
    id: string,
    payload: AgendaSave,
    auth: { accessToken: string; signal?: AbortSignal },
  ) =>
    api.request(
      `/api/v1/meetings/${id}/agenda`,
      savedAgendaSchema,
      { method: "PUT", body: JSON.stringify(payload) },
      auth,
    ),
  parse: async (
    text: string,
    accessToken: string,
    signal: AbortSignal,
  ): Promise<ParseResult> => {
    const url = process.env.NEXT_PUBLIC_PARSER_URL;
    if (!url)
      throw new ApiError(
        503,
        "Parsing is unavailable. Enter your agenda manually.",
      );
    if (text.length > 10000)
      throw new ApiError(413, "Use at most 10,000 characters.");
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    let response: Response;
    try {
      response = await fetch(url, {
        method: "POST",
        signal,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ text, today, tz }),
      });
    } catch (error) {
      if (signal.aborted) throw error;
      throw new ApiError(
        0,
        "Could not reach the parser. Enter your agenda manually.",
      );
    }
    if (!response.ok) {
      const messages: Record<number, string> = {
        401: "Your session expired. Sign in again.",
        413: "Use at most 10,000 characters.",
        422: "Could not parse an agenda. Review the text or enter it manually.",
        429: "Too many requests. Wait a minute and try again.",
      };
      throw new ApiError(
        response.status,
        messages[response.status] ??
          "Parsing unavailable. Enter your agenda manually.",
      );
    }
    const validated = parseResultSchema.safeParse(await response.json());
    if (!validated.success)
      throw new ApiError(
        422,
        "The suggestion has invalid fields. Enter your agenda manually.",
      );
    const result = validated.data;
    signal.throwIfAborted();
    return result;
  },
};
