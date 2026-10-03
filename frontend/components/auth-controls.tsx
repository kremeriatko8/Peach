"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "react-oidc-context";
import { useAuthReady } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { cognitoLogoutUrl } from "@/lib/auth";

function SignedInControls() {
  const auth = useAuth();
  const [signingOut, setSigningOut] = useState(false);
  const [error, setError] = useState(false);
  if (auth.isLoading || auth.activeNavigator)
    return (
      <span className="text-xs text-muted-foreground">Loading account…</span>
    );
  if (!auth.isAuthenticated)
    return (
      <Button asChild variant="outline" size="sm">
        <Link href="/login/">Sign in</Link>
      </Button>
    );
  async function signOut() {
    setSigningOut(true);
    setError(false);
    try {
      const url = cognitoLogoutUrl();
      await auth.removeUser();
      window.location.assign(url);
    } catch {
      setSigningOut(false);
      setError(true);
    }
  }
  return (
    <>
      <span className="max-w-32 truncate sm:max-w-48 text-sm text-muted-foreground">
        {auth.user?.profile.email ?? "Signed in"}
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={signingOut}
        onClick={() => void signOut()}
      >
        Sign out
      </Button>
      {error && (
        <span role="alert" className="text-xs text-destructive">
          Could not sign out. Please try again.
        </span>
      )}
    </>
  );
}

export function AuthControls() {
  const ready = useAuthReady();
  return (
    <div className="ml-auto flex items-center gap-3">
      {ready ? (
        <SignedInControls />
      ) : (
        <Button asChild variant="outline" size="sm">
          <Link href="/login/">Sign in</Link>
        </Button>
      )}
    </div>
  );
}
