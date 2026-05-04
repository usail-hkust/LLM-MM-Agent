"use client";

import React, { useState, useEffect } from "react";
import { RenderAtomProps } from "@/app/domain/abp";
import { useMediaQuery } from "@/app/hooks/useMediaQuery";
import { Group, Panel, useDefaultLayout } from "react-resizable-panels";
import { ResizeHandle } from "@/app/components/layout/ResizableHandle";
import { clientLayoutStorage } from "@/lib/layoutStorage";

export const SplitLayout: React.FC<RenderAtomProps> = ({
  children,
  block,
  blockId,
}) => {
  const layoutConfig = block.layout || block.meta || {};
  const childArray = React.Children.toArray(children);
  const left = childArray[0];
  const right = childArray[1];
  const isMobile = useMediaQuery("(max-width: 1024px)");
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const initialRatio = layoutConfig.initial_split || layoutConfig.initialSplit || 50;
  const { defaultLayout, onLayoutChange } = useDefaultLayout({
    id: `split-layout-${blockId}`,
    storage: clientLayoutStorage,
    panelIds: ["left", "right"],
  });

  if (childArray.length < 2) {
    return <div className="h-full w-full p-4 text-red-500">SplitLayout requires 2 children</div>;
  }

  if (isMobile) {
    return (
      <div className="flex flex-col w-full h-full overflow-hidden">
        <div className="h-[50%] w-full overflow-hidden border-b border-slate-200">
          {left}
        </div>
        <div className="h-[50%] w-full overflow-hidden bg-slate-50">
          {right}
        </div>
      </div>
    );
  }

  if (!mounted) return null;

  return (
    <div className="flex flex-col w-full h-full overflow-hidden">
      <div className="flex-1 min-h-0 relative">
        <Group
          orientation="horizontal"
          defaultLayout={defaultLayout}
          onLayoutChange={onLayoutChange}
        >
          <Panel
            id="left"
            defaultSize={initialRatio}
            minSize={20}
            className="overflow-hidden"
          >
            <div className="h-full w-full overflow-hidden">{left}</div>
          </Panel>
          <ResizeHandle className="bg-slate-50 hover:bg-blue-50" />
          <Panel id="right" minSize={20} className="overflow-hidden">
            <div className="h-full w-full overflow-hidden bg-slate-50/50">
              {right}
            </div>
          </Panel>
        </Group>
      </div>
    </div>
  );
};
