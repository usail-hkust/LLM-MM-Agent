"use client";
import React, { useMemo } from "react";
import { BlockType } from "@/app/api/enums";
import { AtomCode } from "./widgets/atoms/AtomCode";
import { AtomInput } from "./widgets/atoms/AtomInput";
import { AtomData } from "./widgets/atoms/AtomData";
import { AtomArtifacts } from "./widgets/atoms/AtomArtifacts";
import { StackLayout } from "./widgets/layout/StackLayout";
import { GridLayout } from "./widgets/layout/GridLayout";
import { MarkdownDisplay } from "@/app/components/shared/MarkdownDisplay";
import { ContentBlock, RenderAction, SELF_CONTAINED_RENDER_TYPES, ActionScope, RenderAtomProps, resolveBindingKey } from "@/app/domain/abp";
import { getWidgetComponent } from "./WidgetRegistry";
import { useDockActions } from "@/app/hooks/useDockActions";

export function BlockRenderer(props: { 
    block: ContentBlock, 
    onAction: (a: RenderAction) => void, 
    isReadOnly: boolean, 
    isSubmitting: boolean 
}) {
  const { block } = props;
  const isSelfContained = block.render_type && SELF_CONTAINED_RENDER_TYPES.has(block.render_type);

  // [FIX] Action Splitting Strategy
  const { dockActions, localActions } = useMemo(() => {
    const rawActions = block.actions || [];
    if (isSelfContained) return { dockActions: [], localActions: rawActions };

    return {
        // WORKSPACE actions go to the Dock
        dockActions: rawActions.filter(a => a.scope === ActionScope.WORKSPACE),
        // BLOCK actions stay local (default if undefined to keep context local)
        localActions: rawActions.filter(a => !a.scope || a.scope === ActionScope.BLOCK)
    };
  }, [block.actions, isSelfContained]);

  // Register Global Actions to Dock
  useDockActions(dockActions, props.onAction, props.isSubmitting);

  const atomProps: RenderAtomProps = {
    block: block as any,
    state: { read_only: props.isReadOnly, visible: true, data_key: resolveBindingKey(block) || undefined },
    actions: localActions, // [FIX] Pass only local actions
    onAction: props.onAction,
    isSubmitting: props.isSubmitting,
    blockId: block.id
  };

  // Widget Registry
  const Widget = getWidgetComponent(block as any);
  if (Widget) {
      return (
          <Widget {...atomProps}>
             {block.children?.map((child) => (
                <BlockRenderer key={child.id} block={child} onAction={props.onAction} isReadOnly={props.isReadOnly} isSubmitting={props.isSubmitting} />
             ))}
          </Widget>
      );
  }

  // Fallback Components
  if (block.type === BlockType.CODE) return <AtomCode {...atomProps} />;
  if (block.type === BlockType.DATA) return <AtomData {...atomProps} />;
  if (block.type === BlockType.FILE) return <AtomArtifacts {...atomProps} />;
  
  if (block.type === BlockType.CONTAINER) {
     const Layout = block.meta?.layout_kind === "GRID" ? GridLayout : StackLayout;
     const { block: _, ...otherProps } = props;
     return <Layout block={block}>{block.children?.map((c: any) => <BlockRenderer key={c.id} block={c} {...otherProps}/>)}</Layout>;
  }

  return (
      <div className="bg-white p-4 rounded-lg border shadow-sm">
          <MarkdownDisplay content={String(block.content)} />
      </div>
  );
}
