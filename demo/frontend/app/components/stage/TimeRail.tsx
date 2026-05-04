"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowRight, User, Bot } from "lucide-react";
import { useStageStore } from "@/lib/stores";
import { type HistoryVersion } from "@/app/types";
import { VersionCapsule } from "./VersionCapsule";

interface TimeRailProps {
  timeline: HistoryVersion[];
}

const timeFormatter = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

export function TimeRail({ timeline }: TimeRailProps) {
  const { selectedVersionIndex, timeTravel, isHead } = useStageStore();
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Tooltip State
  const [hoveredVersion, setHoveredVersion] = useState<HistoryVersion | null>(null);
  const [tooltipX, setTooltipX] = useState<number>(0);

  useEffect(() => {
    if (isHead && scrollContainerRef.current) {
      requestAnimationFrame(() => {
        if (scrollContainerRef.current) {
          scrollContainerRef.current.scrollTo({
            left: scrollContainerRef.current.scrollWidth,
            behavior: "smooth",
          });
        }
      });
    }
  }, [isHead, timeline.length]);

  const handleSelect = (index: number, isLatest: boolean) => {
    if (isLatest) {
      timeTravel(null);
    } else {
      timeTravel(index);
    }
  };

  const handleMouseEnter = (version: HistoryVersion, e: React.MouseEvent<HTMLElement>) => {
    const railRoot = scrollContainerRef.current?.parentElement;
    if (railRoot) {
      const railRect = railRoot.getBoundingClientRect();
      const targetRect = e.currentTarget.getBoundingClientRect();
      // Calculate center of target relative to the Rail container
      const relativeX = targetRect.left - railRect.left + targetRect.width / 2;
      setTooltipX(relativeX);
      setHoveredVersion(version);
    }
  };

  const handleMouseLeave = () => {
    setHoveredVersion(null);
  };

  return (
    <div className="w-full h-full flex items-center relative group/rail">
      <div className="absolute left-0 right-0 top-1/2 h-px bg-slate-200 z-0 mx-4" />

      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-x-auto flex items-center px-4 gap-4 scrollbar-none relative z-10 h-full snap-x"
        style={{ scrollBehavior: "smooth" }}
      >
        {timeline.map((ver, idx) => {
          const isLatest = idx === timeline.length - 1;
          // [FIX] 修复最新节点的选中逻辑
          // 如果 selectedVersionIndex 具体匹配，或者 (处于 Head 模式 且 当前是最新节点)
          const isSelected = 
            selectedVersionIndex === ver.version_index || 
            (selectedVersionIndex === null && isLatest);

          return (
            <div key={ver.version_index} className="flex items-center gap-1 shrink-0 snap-center">
              <VersionCapsule
                version={ver}
                isSelected={isSelected}
                isLatest={isLatest}
                isHeadMode={isHead}
                onClick={() => handleSelect(ver.version_index, isLatest)}
                onMouseEnter={(e) => handleMouseEnter(ver, e)}
                onMouseLeave={handleMouseLeave}
              />

              {!isLatest && <ArrowRight className="w-3 h-3 text-slate-300 shrink-0 opacity-50" />}
            </div>
          );
        })}

        {timeline.length === 0 && <span className="text-xs text-slate-400 italic pl-2">Timeline initializing...</span>}

        <div className="w-4 shrink-0" />
      </div>

      <div className="absolute left-0 top-0 bottom-0 w-8 bg-gradient-to-r from-white to-transparent pointer-events-none z-20" />
      <div className="absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-white to-transparent pointer-events-none z-20" />

      {/* Floating Tooltip Rendered Outside Scroll Container */}
      {hoveredVersion && (
        <FloatingTooltip version={hoveredVersion} x={tooltipX} />
      )}
    </div>
  );
}

function FloatingTooltip({ version, x }: { version: HistoryVersion; x: number }) {
  const { status_override, trigger, timestamp, status } = version;
  // [REFACTORED] Determine if user action based on trigger
  const isUserAction = trigger === "SELECT" || trigger === "REFINE" || trigger === "EDIT";

  return (
    <div
      className="absolute top-full mt-3 z-50 pointer-events-none animate-in fade-in zoom-in-95 duration-150"
      style={{ left: x, transform: "translateX(-50%)" }}
    >
      <div className="bg-slate-800 text-white text-[10px] py-1.5 px-3 rounded-lg shadow-xl flex flex-col items-center gap-1 min-w-[120px]">
        <div className="flex items-center gap-1.5 font-bold border-b border-white/10 pb-1 mb-0.5 w-full justify-center">
          {isUserAction ? <User className="w-3 h-3" /> : <Bot className="w-3 h-3" />}
          <span>{isUserAction ? "Human-in-the-Loop" : "Automated"}</span>
        </div>
        <span className="font-mono text-slate-300">{timeFormatter.format(new Date(timestamp))}</span>
        <span className="opacity-70 text-[9px] capitalize">
          {status_override
            ? status_override.replace(/_/g, " ").toLowerCase()
            : (status || "Completed").toLowerCase()}
        </span>
      </div>
      <div className="w-2 h-2 bg-slate-800 rotate-45 absolute -top-1 left-1/2 -translate-x-1/2" />
    </div>
  );
}
