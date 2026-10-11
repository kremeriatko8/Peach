import { z } from "zod";

/** Browser code must reach the API through the published port; server components
 *  resolve the Compose service name instead. */
export function apiBaseUrl(): string {
  if (typeof window === "undefined") {
    return process.env.INTERNAL_API_URL ?? "http://backend:8000";
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
  auth?: ItemAuth,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      ...init,
      cache: "no-store",
      signal: auth?.signal,
      headers: {
        "Content-Type": "application/json",
        ...(auth ? { Authorization: `Bearer ${auth.accessToken}` } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch (error) {
    if (auth?.signal?.aborted) throw error;
    throw new ApiError(0, "Could not reach the API");
  }

  if (!response.ok) {
    const detail = await response
      .json()
      .then((body) => (typeof body?.detail === "string" ? body.detail : null))
      .catch(() => null);
    throw new ApiError(
      response.status,
      detail ?? `Request failed (${response.status})`,
    );
  }

  if (response.status === 204) {
    return schema.parse(undefined);
  }
  return schema.parse(await response.json());
}

/* --- schemas mirroring the API contract in README section 5 --- */

export const itemStatuses = ["todo", "in_progress", "done"] as const;
export const itemStatusSchema = z.enum(itemStatuses);

export const itemSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  status: itemStatusSchema,
  created_at: z.string(),
  updated_at: z.string(),
});

export const itemListSchema = z.object({
  items: z.array(itemSchema),
  total: z.number().int(),
});

export const healthSchema = z.object({
  status: z.string(),
  database: z.string(),
});

export const itemInputSchema = z.object({
  name: z.string().min(1, "Name is required").max(120, "Name is too long"),
  description: z.string().max(2000, "Description is too long").optional(),
  status: itemStatusSchema,
});

export type ItemStatus = z.infer<typeof itemStatusSchema>;
export type Item = z.infer<typeof itemSchema>;
export type ItemList = z.infer<typeof itemListSchema>;
export type Health = z.infer<typeof healthSchema>;
export type ItemInput = z.infer<typeof itemInputSchema>;

/* --- meetings --- */

export const meetingSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  starts_at: z.string().datetime({ offset: true }),
  duration_minutes: z.number().int().min(1).max(1440),
  participant_count: z.number().int().min(1).max(10000),
  notes: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
export const meetingListSchema = z.object({
  meetings: z.array(meetingSchema),
  total: z.number().int().nonnegative(),
});
export const meetingInputSchema = z.object({
  title: z
    .string()
    .trim()
    .min(1, "Title is required")
    .max(120, "Title is too long"),
  starts_at: z
    .string()
    .datetime({ offset: true, message: "Choose a valid start time" }),
  duration_minutes: z.number().int().min(1).max(1440),
  participant_count: z.number().int().min(1).max(10000),
  notes: z.string().max(2000, "Notes are too long").nullable().optional(),
});
export type Meeting = z.infer<typeof meetingSchema>;
export type MeetingList = z.infer<typeof meetingListSchema>;
export type MeetingInput = z.infer<typeof meetingInputSchema>;

/* --- endpoints --- */

export type ItemAuth = { accessToken: string; signal?: AbortSignal };
function requireToken(auth: ItemAuth): ItemAuth {
  if (!auth?.accessToken)
    throw new ApiError(401, "Sign in to access your tasks");
  return auth;
}

export const api = {
  listMeetings: (
    params: { limit?: number; offset?: number },
    auth: ItemAuth,
  ) => {
    const query = new URLSearchParams();
    if (params.limit !== undefined) query.set("limit", String(params.limit));
    if (params.offset !== undefined) query.set("offset", String(params.offset));
    const suffix = query.size > 0 ? `?${query}` : "";
    return request(
      `/api/v1/meetings${suffix}`,
      meetingListSchema,
      undefined,
      requireToken(auth),
    );
  },
  getMeeting: (id: string, auth: ItemAuth) =>
    request(
      `/api/v1/meetings/${encodeURIComponent(id)}`,
      meetingSchema,
      undefined,
      requireToken(auth),
    ),
  createMeeting: (payload: MeetingInput, auth: ItemAuth) =>
    request(
      "/api/v1/meetings",
      meetingSchema,
      { method: "POST", body: JSON.stringify(payload) },
      requireToken(auth),
    ),
  updateMeeting: (id: string, payload: Partial<MeetingInput>, auth: ItemAuth) =>
    request(
      `/api/v1/meetings/${encodeURIComponent(id)}`,
      meetingSchema,
      { method: "PATCH", body: JSON.stringify(payload) },
      requireToken(auth),
    ),
  deleteMeeting: (id: string, auth: ItemAuth) =>
    request(
      `/api/v1/meetings/${encodeURIComponent(id)}`,
      z.undefined(),
      { method: "DELETE" },
      requireToken(auth),
    ),

  readiness: () => request("/api/v1/health/ready", healthSchema),

  listItems: (params: { limit?: number; offset?: number }, auth: ItemAuth) => {
    const query = new URLSearchParams();
    if (params.limit !== undefined) query.set("limit", String(params.limit));
    if (params.offset !== undefined) query.set("offset", String(params.offset));
    const suffix = query.size > 0 ? `?${query}` : "";
    return request(
      `/api/v1/items${suffix}`,
      itemListSchema,
      undefined,
      requireToken(auth),
    );
  },

  createItem: (payload: ItemInput, auth: ItemAuth) =>
    request(
      "/api/v1/items",
      itemSchema,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      requireToken(auth),
    ),

  updateItem: (id: string, payload: Partial<ItemInput>, auth: ItemAuth) =>
    request(
      `/api/v1/items/${id}`,
      itemSchema,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
      requireToken(auth),
    ),

  deleteItem: (id: string, auth: ItemAuth) =>
    request(
      `/api/v1/items/${id}`,
      z.undefined(),
      { method: "DELETE" },
      requireToken(auth),
    ),
};
