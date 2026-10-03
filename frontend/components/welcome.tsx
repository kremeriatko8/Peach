"use client";

import { ArrowRight, Check, LayoutGrid, Sparkles } from "lucide-react";
import { useState } from "react";
import { useAuth } from "react-oidc-context";
import { Button } from "@/components/ui/button";
import { itemStatuses } from "@/lib/api";
import { statusMeta } from "@/lib/item-status";

export function Welcome() {
  const auth = useAuth();
  const [failed, setFailed] = useState(false);
  const [starting, setStarting] = useState(false);
  async function signIn() {
    setFailed(false);
    setStarting(true);
    try {
      await auth.signinRedirect();
    } catch {
      setFailed(true);
      setStarting(false);
    }
  }
  return (
    <div className="relative grid min-h-[65vh] items-center gap-16 py-8 lg:grid-cols-[1.1fr_1fr] lg:gap-12">
      <div className="relative z-10">
        <span aria-hidden className="mb-8 block text-7xl">
          🍑
        </span>
        <p className="mb-4 text-xs font-semibold tracking-[0.2em] text-tint-peach-foreground uppercase">
          A little clarity. A little progress.
        </p>
        <h1 className="text-5xl leading-[1.08] font-semibold sm:text-6xl">
          Welcome to <span className="text-primary">Peach</span>
        </h1>
        <p className="mt-6 max-w-md text-lg leading-8 text-muted-foreground">
          A simple and visual way to organize your tasks, track your progress,
          and keep everything in one place.
        </p>
        <Button
          size="lg"
          className="mt-8 h-12 rounded-xl px-7 text-base shadow-sm"
          disabled={starting || !!auth.activeNavigator}
          onClick={() => void signIn()}
        >
          Sign in <ArrowRight className="ml-2 size-4" />
        </Button>
        {failed && (
          <p role="alert" className="mt-3 text-sm text-destructive">
            Could not start sign in. Please try again.
          </p>
        )}
        <p className="mt-4 text-xs text-muted-foreground">
          New here? Create your account on the sign-in page.
        </p>
        <div className="mt-10 grid gap-3 text-sm text-muted-foreground">
          <span className="flex items-center gap-3">
            <LayoutGrid className="size-4 text-primary" />
            Organize your tasks
          </span>
          <span className="flex items-center gap-3">
            <Check className="size-4 text-tint-green-foreground" />
            Track your progress
          </span>
          <span className="flex items-center gap-3">
            <Sparkles className="size-4 text-tint-blue-foreground" />
            All in one workspace
          </span>
        </div>
      </div>
      <div className="relative" aria-label="An illustration of a task board">
        <div
          aria-hidden
          className="absolute -inset-8 -z-0 rounded-full bg-linear-to-br from-tint-peach via-[#f6f2ff] to-tint-blue blur-2xl"
        />
        <div className="relative rounded-3xl border border-border bg-white/95 p-5 shadow-[0_15px_50px_-20px_rgba(80,50,40,0.15)] sm:p-7">
          <div className="mb-6 flex items-center justify-between">
            <span className="font-semibold">A place for every task</span>
            <span aria-hidden className="text-xl">
              🍑
            </span>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {itemStatuses.map((status, index) => (
              <div
                key={status}
                className={`min-h-52 rounded-2xl p-3 ${statusMeta[status].column}`}
              >
                <p className="mb-4 text-[11px] font-semibold">
                  {statusMeta[status].label}
                </p>
                {Array.from({ length: index === 1 ? 2 : 1 }, (_, row) => (
                  <div
                    aria-hidden
                    key={row}
                    className="mb-3 rounded-xl border border-white bg-white p-3 shadow-xs"
                  >
                    <div
                      className={`mb-3 size-5 rounded-md ${statusMeta[status].pill}`}
                    />
                    <div className="mb-2 h-1.5 w-full rounded-full bg-border" />
                    <div className="h-1.5 w-2/3 rounded-full bg-border/60" />
                  </div>
                ))}
              </div>
            ))}
          </div>
          <p className="mt-5 text-xs text-muted-foreground">
            From a fresh idea to a satisfying done.
          </p>
        </div>
      </div>
    </div>
  );
}
