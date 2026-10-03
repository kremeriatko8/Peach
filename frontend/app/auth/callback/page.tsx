"use client";

import Link from "next/link";
import { hasAuthParams, useAuth } from "react-oidc-context";
import { useAuthReady } from "@/components/auth-provider";
import { PageHeader } from "@/components/page-header";

function CallbackStatus() {
  const auth = useAuth();
  if (auth.error)
    return (
      <p role="alert">
        Sign in could not be completed.{" "}
        <Link className="underline" href="/login/">
          Try again
        </Link>
        .
      </p>
    );
  if (!auth.isLoading && !hasAuthParams())
    return (
      <p>
        No sign-in response was found.{" "}
        <Link className="underline" href="/">
          Return to Peach
        </Link>
        .
      </p>
    );
  return <p className="text-sm text-muted-foreground">Completing sign in…</p>;
}

export default function CallbackPage() {
  const ready = useAuthReady();
  return (
    <div className="grid gap-6">
      <PageHeader title="Signing in" />
      {ready ? (
        <CallbackStatus />
      ) : (
        <p className="text-sm text-muted-foreground">
          Loading authentication configuration…
        </p>
      )}
    </div>
  );
}
