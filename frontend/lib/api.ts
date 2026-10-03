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

/* --- endpoints --- */

export type ItemAuth = { accessToken: string; signal?: AbortSignal };
function requireToken(auth: ItemAuth): ItemAuth {
  if (!auth?.accessToken)
    throw new ApiError(401, "Sign in to access your tasks");
  return auth;
}

export const api = {
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
