"use client";
import { cn } from "@/lib/utils";
export function StackLayout({ block, children }: any) {
  const gap = block.meta?.gap || 4;
  const gapClass = gap === 2 ? "gap-2" : gap === 3 ? "gap-3" : gap === 4 ? "gap-4" : gap === 6 ? "gap-6" : gap === 8 ? "gap-8" : "gap-4";
  return <div className={cn("flex w-full h-full min-h-0", block.meta?.orientation === "horizontal" ? "flex-row" : "flex-col", gapClass)}>{children}</div>;
}
