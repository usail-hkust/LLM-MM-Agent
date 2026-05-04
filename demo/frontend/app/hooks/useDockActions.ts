"use client";

import { useEffect, useRef, useId } from "react";
import { useDockStore, DockAction } from "@/lib/stores";
import { useFormContext } from "react-hook-form";
import { RenderAction, ActionType } from "@/app/api/schemas";
import * as Icons from "lucide-react";

// Global Registry
const actionRegistry = new Map<string, DockAction[]>();

const syncGlobalStore = (
  setRightActions: (actions: DockAction[]) => void,
  currentRightActions: DockAction[] // [FIX] Compare with current state
) => {
  const rawActions = Array.from(actionRegistry.values()).flat();

  // Deduplicate by ID
  const uniqueActionsMap = new Map<string, DockAction>();
  rawActions.forEach((action) => {
    if (!uniqueActionsMap.has(action.id)) {
      uniqueActionsMap.set(action.id, action);
    }
  });

  const nextActions = Array.from(uniqueActionsMap.values());

  // [FIX] Deep comparison to prevent loop
  const isChanged =
    nextActions.length !== currentRightActions.length ||
    nextActions.some((a, i) => {
      const b = currentRightActions[i];
      // Compare critical fields that trigger Re-renders
      return (
        a.id !== b.id ||
        a.label !== b.label ||
        a.disabled !== b.disabled ||
        a.loading !== b.loading
      );
    });

  if (isChanged) {
    setRightActions(nextActions);
  }
};

export function useDockActions(
  actions: RenderAction[],
  onAction: (action: RenderAction) => void,
  isSubmitting: boolean,
  status?: string // [NEW] Accept status for global disabling
) {
  const id = useId();
  const setRightActions = useDockStore((state) => state.setRightActions);
  const rightActions = useDockStore((state) => state.rightActions); // [FIX] Read current state
  // We don't reset center content automatically anymore to avoid fighting with other components

  const formContext = useFormContext();
  const isDirty = formContext?.formState?.isDirty ?? false;

  const onActionRef = useRef(onAction);
  useEffect(() => { onActionRef.current = onAction; }, [onAction]);

  // Serialize actions to prevent infinite loop on object identity change
  const actionsKey = JSON.stringify(actions);

  useEffect(() => {
    if (!actions || actions.length === 0) {
      if (actionRegistry.has(id)) {
        actionRegistry.delete(id);
        const currentActions = useDockStore.getState().rightActions;
        syncGlobalStore(setRightActions, currentActions);
      }
      return;
    }

    const dockActions: DockAction[] = actions.map((a) => {
      // [FIX] Global Disabling Strategy
      // 1. If we are currently submitting an interaction ID (optimistic)
      // 2. OR If the backend status is DRAFTING/RUNNING (AI is working)
      let isDisabled = isSubmitting || status === "DRAFTING" || status === "RUNNING";

      if (a.validation_rule === "require_dirty" && !isDirty) {
        isDisabled = true;
      }

      // Dynamic Icon Lookup
      const IconComponent = a.icon ? (Icons as any)[a.icon] : undefined;

      return {
        id: a.id,
        label: a.label,
        variant:
          a.type === ActionType.DANGER ? "danger" :
            a.type === ActionType.SECONDARY ? "secondary" :
              a.type === ActionType.ICON ? "ghost" : "primary",
        icon: IconComponent,
        onClick: () => {
          const currentFormData = formContext ? formContext.getValues() : {};
          // Merge form data into payload
          const mergedAction: RenderAction = {
            ...a,
            payload: { ...a.payload, ...currentFormData },
          };
          onActionRef.current(mergedAction);
        },
        disabled: isDisabled,
        loading: isSubmitting && a.type === ActionType.PRIMARY,
        tooltip: a.confirm_message || undefined,
      };
    });

    actionRegistry.set(id, dockActions);
    const currentActions = useDockStore.getState().rightActions;
    syncGlobalStore(setRightActions, currentActions);

    return () => {
      actionRegistry.delete(id);
      // We don't necessarily need to sync on unmount if we assume others will sync, 
      // but to be safe we should. However, this cleanup runs BEFORE the next effect setup.
      // So we momentarily have a state where actions are removed.
      // If we don't sync here, the Store keeps stale actions until next sync.
      const current = useDockStore.getState().rightActions;
      syncGlobalStore(setRightActions, current);
    };
  }, [
    id,
    actionsKey,
    isSubmitting,
    isDirty,
    setRightActions,
    status, // [NEW] Re-sync when status changes
    // rightActions REMOVED to prevent loop
  ]);
}
