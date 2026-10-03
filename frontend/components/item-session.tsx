"use client";

import Link from "next/link";
import {
  Fragment,
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "react-oidc-context";
import { useAuthReady } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { api, ApiError, type ItemInput } from "@/lib/api";

export type ItemSession = {
  sub: string;
  accessToken: string;
  signal: AbortSignal;
  unauthorized: () => void;
};
export const ItemSessionContext = createContext<ItemSession | null>(null);
export const ItemAccessStateContext = createContext<
  "loading" | "signed-out" | "expired" | "ready"
>("loading");
const Reauthenticate = createContext<(() => Promise<void>) | null>(null);

class AccountLifetime {
  private controller = new AbortController();
  private active = false;
  constructor(readonly sub: string | undefined) {}
  get signal() {
    return this.controller.signal;
  }
  activate() {
    this.active = true;
  }
  retire(clear: () => void) {
    this.active = false;
    // StrictMode immediately replays setup; do not dispose its live account.
    queueMicrotask(() => {
      if (!this.active) {
        this.controller.abort();
        clear();
      }
    });
  }
}

function ConnectedSession({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const sub = auth.isAuthenticated ? auth.user?.profile.sub : undefined;
  const accessToken = auth.user?.access_token;
  const [rejected, setRejected] = useState<{
    sub: string;
    token: string;
  } | null>(null);
  const lifetime = useMemo(() => new AccountLifetime(sub), [sub]);
  useEffect(() => {
    lifetime.activate();
    return () => {
      lifetime.retire(() => {
        if (sub) {
          void queryClient.cancelQueries({ queryKey: ["items", sub] });
          queryClient.removeQueries({ queryKey: ["items", sub] });
        }
      });
    };
  }, [sub, lifetime, queryClient]);
  const expired =
    !!sub &&
    !!accessToken &&
    rejected?.sub === sub &&
    rejected.token === accessToken;
  const loading = auth.isLoading || !!auth.activeNavigator;
  const session = useMemo(
    () =>
      sub && accessToken && !expired && !loading
        ? {
            sub,
            accessToken,
            get signal() {
              return lifetime.signal;
            },
            unauthorized: () => setRejected({ sub, token: accessToken }),
          }
        : null,
    [sub, accessToken, expired, loading, lifetime],
  );
  return (
    <Reauthenticate.Provider value={() => auth.signinRedirect()}>
      <ItemAccessStateContext.Provider
        value={
          loading
            ? "loading"
            : expired
              ? "expired"
              : session
                ? "ready"
                : "signed-out"
        }
      >
        <ItemSessionContext.Provider value={session}>
          {children}
        </ItemSessionContext.Provider>
      </ItemAccessStateContext.Provider>
    </Reauthenticate.Provider>
  );
}

export function ItemSessionProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const ready = useAuthReady();
  return ready ? <ConnectedSession>{children}</ConnectedSession> : children;
}

export function ItemAccessGate({ children }: { children: React.ReactNode }) {
  const state = useContext(ItemAccessStateContext);
  const session = useContext(ItemSessionContext);
  const signIn = useContext(Reauthenticate);
  const [failed, setFailed] = useState(false);
  if (state === "ready")
    return <Fragment key={session?.sub}>{children}</Fragment>;
  if (state === "loading")
    return (
      <p role="status" className="text-sm text-muted-foreground">
        Getting Peach ready…
      </p>
    );
  return (
    <div className="grid justify-items-start gap-4">
      <p className="text-sm text-muted-foreground">
        {state === "expired"
          ? "Your session needs to be renewed. Sign in again to continue."
          : "Sign in to view your board."}
      </p>
      {state === "expired" && signIn ? (
        <Button onClick={() => void signIn().catch(() => setFailed(true))}>
          Sign in again
        </Button>
      ) : (
        <Button asChild>
          <Link href="/login/">Sign in</Link>
        </Button>
      )}
      {failed && <p role="alert">Could not start sign in. Please try again.</p>}
    </div>
  );
}

export function useItemApi() {
  const session = useContext(ItemSessionContext);
  const execute = async <T,>(operation: () => Promise<T>): Promise<T> => {
    if (!session || session.signal.aborted)
      throw new ApiError(401, "Sign in to access your tasks");
    try {
      return await operation();
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
  const auth = {
    accessToken: session?.accessToken ?? "",
    get signal() {
      return session?.signal;
    },
  };
  return {
    session,
    queryKey: ["items", session?.sub ?? null] as const,
    listItems: (
      params: { limit?: number; offset?: number },
      signal?: AbortSignal,
    ) =>
      execute(() =>
        api.listItems(params, {
          ...auth,
          signal:
            signal && session
              ? AbortSignal.any([signal, session.signal])
              : auth.signal,
        }),
      ),
    createItem: (payload: ItemInput) =>
      execute(() => api.createItem(payload, auth)),
    updateItem: (id: string, payload: Partial<ItemInput>) =>
      execute(() => api.updateItem(id, payload, auth)),
    deleteItem: (id: string) => execute(() => api.deleteItem(id, auth)),
  };
}
