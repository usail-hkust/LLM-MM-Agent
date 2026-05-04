"use client";

import React, { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { RenderAtomProps } from "@/app/domain/abp";

// [CHANGED] Use RenderAtomProps (block is now passed as `data` or `value`, but for meta, direct meta is better)
export const TabsLayout: React.FC<RenderAtomProps> = ({ children, block }) => {
  const layoutConfig = block.layout || {};
  const meta = block.meta || {};
  const childArray = React.Children.toArray(children) as React.ReactElement[];

  const tabs = childArray.map((child: any, index: number) => {
    const childBlock = child.props?.block;
    return {
      label:
        childBlock?.layout?.tabLabel ||
        childBlock?.label ||
        childBlock?.meta?.tabLabel ||
        layoutConfig.tabLabels?.[index] ||
        meta.tabLabels?.[index] ||
        `Tab ${index + 1}`,
      index,
    };
  });

  const [activeTab, setActiveTab] = useState(0);

  useEffect(() => {
    const targetName = layoutConfig.default_tab || meta.default_tab;
    if (!targetName) return;
    const target = tabs.find((tab) => tab.label === targetName);
    if (target) setActiveTab(target.index);
  }, [layoutConfig.default_tab, meta.default_tab, tabs]);

  return (
    <div className="flex flex-col h-full w-full bg-white border-l border-slate-200/50">
      {/* Tab Header */}
      <div className="flex items-center bg-slate-50 border-b border-slate-200 px-2 shrink-0 h-10 gap-1 overflow-x-auto no-scrollbar">
        {tabs.map((tab) => (
          <button
            key={tab.index}
            onClick={() => setActiveTab(tab.index)}
            className={cn(
              "px-4 h-full text-xs font-bold transition-colors relative top-[1px] border-b-2 whitespace-nowrap",
              activeTab === tab.index
                ? "bg-white text-blue-600 border-blue-500"
                : "text-slate-500 hover:bg-slate-100 border-transparent hover:text-slate-700"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-hidden relative bg-white">
        {childArray.map((child, index) => (
          <div
            key={index}
            className={cn(
              "absolute inset-0 w-full h-full overflow-hidden transition-opacity duration-200",
              activeTab === index ? "opacity-100 z-10" : "opacity-0 z-0 pointer-events-none"
            )}
          >
            {child}
          </div>
        ))}
      </div>
    </div>
  );
};
