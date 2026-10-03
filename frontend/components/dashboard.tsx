"use client";

import Link from "next/link";
import { ArrowRight, LayoutGrid } from "lucide-react";
import { useAuth } from "react-oidc-context";
import { HealthBadge } from "@/components/health-badge";
import { ItemSummary } from "@/components/item-summary";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useItems } from "@/lib/items";
import { itemStatuses } from "@/lib/api";
import { statusMeta } from "@/lib/item-status";

export function Dashboard() {
  const auth = useAuth();
  const name = auth.user?.profile.name?.trim();
  const { data, isPending, isError, refetch } = useItems();
  const upNext =
    data?.items.filter((item) => item.status !== "done").slice(0, 5) ?? [];
  return (
    <div className="grid gap-8">
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <p className="mb-3 text-xs font-semibold tracking-[0.16em] text-primary uppercase">
            Your workspace
          </p>
          <h1 className="text-3xl font-semibold sm:text-4xl">
            {name ? `Welcome back, ${name}!` : "Welcome back!"}{" "}
            <span aria-hidden>🍑</span>
          </h1>
          <p className="mt-3 text-sm text-muted-foreground">
            Here&apos;s what&apos;s happening with your tasks. Keep going!
          </p>
        </div>
        <Button asChild className="rounded-xl">
          <Link href="/items">
            <LayoutGrid className="size-4" /> Open board
          </Link>
        </Button>
      </div>
      {isPending ? (
        <div
          role="status"
          aria-label="Loading tasks"
          className="grid gap-4 sm:grid-cols-3"
        >
          {itemStatuses.map((status) => (
            <Skeleton key={status} className="h-44 rounded-2xl" />
          ))}
        </div>
      ) : isError ? (
        <div role="alert" className="rounded-2xl border bg-card p-6">
          <p className="mb-3 text-sm">Your tasks could not be loaded.</p>
          <Button variant="outline" onClick={() => void refetch()}>
            Try again
          </Button>
        </div>
      ) : (
        <>
          <ItemSummary items={data.items} />
          <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
            <section className="rounded-2xl border bg-card p-6 shadow-xs">
              <div className="mb-6 flex items-center justify-between gap-3">
                <h2 className="font-semibold">Up next</h2>
                <Link
                  href="/items"
                  className="flex items-center gap-1 text-xs font-medium text-primary"
                >
                  View board <ArrowRight className="size-3" />
                </Link>
              </div>
              {upNext.length ? (
                <ul className="divide-y divide-border">
                  {upNext.map((item) => (
                    <li
                      key={item.id}
                      className="flex items-center justify-between gap-3 py-4"
                    >
                      <div className="min-w-0">
                        <Link
                          href="/items"
                          className="block truncate text-sm font-medium hover:text-primary"
                        >
                          {item.name}
                        </Link>
                        {item.description && (
                          <p className="mt-1 truncate text-xs text-muted-foreground">
                            {item.description}
                          </p>
                        )}
                      </div>
                      <span
                        className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${statusMeta[item.status].pill}`}
                      >
                        {statusMeta[item.status].label}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="rounded-xl bg-muted p-6 text-center">
                  <p className="mb-2 text-2xl" aria-hidden>
                    🌱
                  </p>
                  <p className="text-sm font-medium">
                    {data.items.length ? "All caught up" : "A fresh start"}
                  </p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {data.items.length
                      ? "No unfinished tasks. View the board to add your next task."
                      : "Add your first task on the board."}
                  </p>
                </div>
              )}
            </section>
            <section className="rounded-2xl border bg-card p-6 shadow-xs">
              <div className="mb-6 flex items-center justify-between">
                <h2 className="font-semibold">Your board</h2>
                <LayoutGrid
                  aria-hidden
                  className="size-4 text-muted-foreground"
                />
              </div>
              <div className="grid grid-cols-3 gap-2 sm:gap-3">
                {itemStatuses.map((status) => (
                  <div
                    key={status}
                    className={`min-h-52 rounded-xl p-2.5 ${statusMeta[status].column}`}
                  >
                    <h3 className="mb-4 text-[11px] font-semibold">
                      {statusMeta[status].label}
                    </h3>
                    {data.items
                      .filter((item) => item.status === status)
                      .slice(0, 3)
                      .map((item) => (
                        <Link
                          key={item.id}
                          href="/items"
                          className="mb-2 block rounded-lg border border-border/50 bg-card p-3 text-xs leading-5 font-medium break-words shadow-xs hover:border-primary/30"
                        >
                          {item.name}
                        </Link>
                      ))}
                    {!data.items.some((item) => item.status === status) && (
                      <p className="text-[11px] text-muted-foreground">
                        No tasks yet
                      </p>
                    )}
                  </div>
                ))}
              </div>
              <p className="mt-4 text-xs text-muted-foreground">
                A quick look at your workspace. Open the board to make changes.
              </p>
            </section>
          </div>
        </>
      )}
      <div className="flex items-center gap-2 border-t border-border/60 pt-5 text-xs text-muted-foreground">
        <span>API status</span>
        <HealthBadge />
      </div>
    </div>
  );
}
