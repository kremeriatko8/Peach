"use client";

import {
  createContext,
  useContext,
  useMemo,
  useSyncExternalStore,
} from "react";
import { AuthProvider } from "react-oidc-context";
import { authConfig } from "@/lib/auth";

const AuthReady = createContext(false);
const subscribe = () => () => {};
export const useAuthReady = () => useContext(AuthReady);

export function PeachAuthProvider({ children }: { children: React.ReactNode }) {
  const mounted = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
  const config = useMemo(() => (mounted ? authConfig() : null), [mounted]);
  if (!config) return children;
  return (
    <AuthProvider {...config}>
      <AuthReady.Provider value>{children}</AuthReady.Provider>
    </AuthProvider>
  );
}
