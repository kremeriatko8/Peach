"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { ItemSessionProvider } from "@/components/item-session";
import { PeachAuthProvider } from "@/components/auth-provider";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 10_000 },
        },
      }),
  );

  return (
    <PeachAuthProvider>
      <QueryClientProvider client={queryClient}>
        <ItemSessionProvider>{children}</ItemSessionProvider>
      </QueryClientProvider>
    </PeachAuthProvider>
  );
}
