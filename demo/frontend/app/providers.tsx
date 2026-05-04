"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { Toaster } from "@/components/ui/sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        // 默认配置：窗口聚焦时重新获取数据，失败重试 1 次
        refetchOnWindowFocus: true, 
        retry: 1,
        staleTime: 1000 * 60 * 5, // 5分钟内数据认为是新鲜的（除非手动 invalidate）
      },
    },
  }));
  const showDevtools = process.env.NODE_ENV === "development";

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster position="top-right" richColors />
      {showDevtools && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}
