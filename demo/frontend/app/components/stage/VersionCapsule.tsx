"use client";

import { cn } from "@/lib/utils";
import { useStatusVariant } from "@/app/hooks/useStatusVariant";
import { type HistoryVersion } from "@/app/types";

interface VersionCapsuleProps {
  version: HistoryVersion;
  isSelected: boolean;
  isLatest: boolean;
  isHeadMode: boolean;
  onClick: () => void;
  // New event handlers for tooltip management
  onMouseEnter?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  onMouseLeave?: () => void;
}

export function VersionCapsule({
  version,
  isSelected,
  isLatest,
  isHeadMode,
  onClick,
  onMouseEnter,
  onMouseLeave,
}: VersionCapsuleProps) {
  // [REFACTORED] Determine actor type based on trigger (user actions like SELECT, REFINE)
  const isUserAction = version.trigger === "SELECT" || version.trigger === "REFINE" || version.trigger === "EDIT";

  const config = useStatusVariant({
    status: version.status,
    statusOverride: version.status_override,
    actorType: isUserAction ? "user" : "bot",
    isHead: isHeadMode && isLatest,
    versionIndex: version.version_index,
  });

  const { theme, animation, variant } = config;

  const baseStyles =
    "relative flex items-center gap-2 px-3 py-1.5 rounded-full border transition-all duration-200 cursor-pointer select-none group shrink-0";

  const selectedStyles = "ring-2 ring-offset-1 ring-black border-black/10 z-10 shadow-md transform scale-105 bg-white";
  const isPhantomActive = isHeadMode && isLatest && (variant === "running" || variant === "pending");

  return (
    <button
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className={cn(
        baseStyles,
        isSelected ? selectedStyles : cn(theme.bg, theme.border, theme.text),
        isPhantomActive && "ring-2 ring-offset-1 ring-blue-100 border-blue-400",
        "min-w-[80px] justify-center",
      )}
    >
      {variant === "running" && (
        <span
          className={cn(
            "absolute inset-0 rounded-full border animate-ping opacity-20 pointer-events-none",
            theme.border
          )}
        />
      )}

      <div className="flex flex-col items-start leading-none">
        <span className="text-[10px] font-bold font-mono tracking-tight">v{version.version_index}</span>
        {(variant === "running" || variant === "pending") && (
          <span className="text-[8px] font-bold uppercase tracking-wider opacity-80 mt-0.5">
            {variant === "running" ? "Exec" : "Action"}
          </span>
        )}
      </div>

      {/* 
         FIX: Removed internal tooltip to prevent clipping. 
         Tooltip is now handled by the parent TimeRail component. 
      */}
    </button>
  );
}
