"use client";

import { useContext } from "react";
import { useQuery } from "@tanstack/react-query";
import { ItemSessionContext } from "@/components/item-session";
import { api, ApiError, type MeetingInput } from "@/lib/api";

export function useMeetingApi() {
  const session = useContext(ItemSessionContext);
  const execute = async <T>(operation: () => Promise<T>): Promise<T> => {
    if (!session || session.signal.aborted)
      throw new ApiError(401, "Sign in to access your meetings");
    try {
      const result = await operation();
      session.signal.throwIfAborted();
      return result;
    } catch (error) {
      if (
        !session.signal.aborted &&
        error instanceof ApiError &&
        error.status === 401
      )
        session.unauthorized();
      throw error;
    }
  };
  const auth = (signal?: AbortSignal) => ({
    accessToken: session?.accessToken ?? "",
    signal:
      signal && session
        ? AbortSignal.any([signal, session.signal])
        : session?.signal,
  });
  return {
    session,
    queryKey: ["meetings", session?.sub ?? null] as const,
    listMeetings: (
      params: { limit?: number; offset?: number },
      signal?: AbortSignal,
    ) => execute(() => api.listMeetings(params, auth(signal))),
    createMeeting: (payload: MeetingInput) =>
      execute(() => api.createMeeting(payload, auth())),
    updateMeeting: (id: string, payload: Partial<MeetingInput>) =>
      execute(() => api.updateMeeting(id, payload, auth())),
    deleteMeeting: (id: string) => execute(() => api.deleteMeeting(id, auth())),
  };
}

export const MEETINGS_PAGE_SIZE = 20;
export function useMeetings(page: number) {
  const client = useMeetingApi();
  return useQuery({
    queryKey: [...client.queryKey, page],
    enabled: !!client.session,
    queryFn: ({ signal }) =>
      client.listMeetings(
        { limit: MEETINGS_PAGE_SIZE, offset: page * MEETINGS_PAGE_SIZE },
        signal,
      ),
    retry: (count, error) =>
      !(error instanceof ApiError && error.status === 401) && count < 1,
  });
}
