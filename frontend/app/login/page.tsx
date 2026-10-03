"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { hasAuthParams, useAuth } from "react-oidc-context";
import { useAuthReady } from "@/components/auth-provider";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";

function LoginFlow() {
  const auth = useAuth();
  const started = useRef(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (
      auth.isLoading ||
      auth.activeNavigator ||
      auth.error ||
      hasAuthParams() ||
      started.current
    )
      return;
    if (auth.isAuthenticated) {
      window.location.replace("/");
      return;
    }
    started.current = true;
    void auth.signinRedirect().catch(() => setFailed(true));
  }, [auth]);
  if (failed || auth.error)
    return (
      <div className="grid justify-items-start gap-3">
        <p role="alert">Sign in failed. Please try again.</p>
        <Button
          disabled={!!auth.activeNavigator}
          onClick={() => {
            window.history.replaceState({}, document.title, "/login/");
            setFailed(false);
            void auth.signinRedirect().catch(() => setFailed(true));
          }}
        >
          Try again
        </Button>
      </div>
    );
  return (
    <p className="text-sm text-muted-foreground">Redirecting to sign in…</p>
  );
}

export default function LoginPage() {
  const ready = useAuthReady();
  return (
    <div className="grid gap-6">
      <PageHeader
        title="Sign in"
        description="Sign in or create an account with email and password, or use Google."
      />
      {ready ? (
        <LoginFlow />
      ) : (
        <p className="text-sm text-muted-foreground">
          Sign in is unavailable until authentication is configured.
        </p>
      )}
      <Button asChild variant="outline" className="justify-self-start">
        <Link href="/">Back to Peach</Link>
      </Button>
    </div>
  );
}
