"use client";

import { useAuth } from "react-oidc-context";
import { useAuthReady } from "@/components/auth-provider";
import { ItemAccessGate } from "@/components/item-session";
import { Dashboard } from "@/components/dashboard";
import { Welcome } from "@/components/welcome";

function Loading() {
  return (
    <div
      role="status"
      className="grid min-h-[55vh] place-content-center justify-items-center gap-4"
    >
      <span aria-hidden className="text-4xl">
        🍑
      </span>
      <p className="text-sm text-muted-foreground">Getting Peach ready…</p>
    </div>
  );
}

function AuthenticatedHome() {
  const auth = useAuth();
  if (auth.isLoading || auth.activeNavigator) return <Loading />;
  return auth.isAuthenticated ? (
    <ItemAccessGate>
      <Dashboard />
    </ItemAccessGate>
  ) : (
    <Welcome />
  );
}

export default function HomePage() {
  const ready = useAuthReady();
  return ready ? <AuthenticatedHome /> : <Loading />;
}
