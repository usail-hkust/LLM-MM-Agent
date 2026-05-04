"use client";

import { Separator } from "react-resizable-panels";
import { GripVertical } from "lucide-react";
import { cn } from "@/lib/utils";

interface ResizeHandleProps {
  className?: string;
  id?: string;
}

export function ResizeHandle({ className, id }: ResizeHandleProps) {
  return (
    <Separator
      id={id}
      className={cn(
        "group flex w-1.5 items-center justify-center bg-transparent transition-colors hover:bg-slate-200 outline-none focus-visible:ring-1 focus-visible:ring-blue-500 active:bg-blue-500 active:w-1 z-50 cursor-col-resize",
        className
      )}
    >
      <div className="z-10 flex h-4 w-1 items-center justify-center rounded-sm bg-slate-300 transition-colors group-hover:bg-slate-400 group-active:bg-white">
        <GripVertical className="h-2.5 w-2.5 opacity-0 group-hover:opacity-100 group-active:opacity-100 transition-opacity text-slate-600 group-active:text-blue-600" />
      </div>
    </Separator>
  );
}
