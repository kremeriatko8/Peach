"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "react-oidc-context";
import { useAuthReady } from "@/components/auth-provider";

import { AuthControls } from "@/components/auth-controls";

import { cn } from "@/lib/utils";

const links = [
  { href: "/", label: "Dashboard" },
  { href: "/items", label: "Board" },
];

function AccountNavigation() {
  const pathname = usePathname();
  const auth = useAuth();
  if (auth.isLoading || auth.activeNavigator) return null;
  return (
    <>
      {auth.isAuthenticated && (
        <nav
          aria-label="Primary navigation"
          className="flex items-center gap-1 text-sm"
        >
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={
                (
                  link.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(link.href)
                )
                  ? "page"
                  : undefined
              }
              className={cn(
                "rounded-lg px-2.5 py-1.5 font-medium transition-colors",
                (
                  link.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(link.href)
                )
                  ? "bg-accent text-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>
      )}
      <AuthControls />
    </>
  );
}

export function SiteHeader() {
  const ready = useAuthReady();
  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/90 backdrop-blur-md">
      <div className="mx-auto flex min-h-18 w-full max-w-5xl flex-wrap items-center gap-x-4 gap-y-3 px-6 py-3 sm:gap-x-8 sm:px-8">
        <Link href="/" className="mr-auto flex items-center gap-2">
          <span aria-hidden className="text-2xl">
            🍑
          </span>
          <span className="font-heading text-lg font-semibold tracking-tight">
            Peach
          </span>
        </Link>
        {ready && <AccountNavigation />}
      </div>
    </header>
  );
}
