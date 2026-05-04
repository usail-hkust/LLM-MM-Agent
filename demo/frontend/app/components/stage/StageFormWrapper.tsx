"use client";
import { ReactNode, useEffect, useRef } from "react";
import { useForm, FormProvider } from "react-hook-form";
import { hydrateFormFromABP } from "@/app/lib/abp-utils";

interface StageFormWrapperProps {
  version: any; // Accepts HistoryVersion or a pseudo-version object
  children: ReactNode;
}

export function StageFormWrapper({ version, children }: StageFormWrapperProps) {
  const methods = useForm({
    mode: "onChange",
    defaultValues: { new_content: {} },
  });

  // Track the current Context Identity to distinguish between 
  // "Data Refresh" (same node/version) and "Navigation" (diff node/version)
  const contextIdRef = useRef<string>("");

  useEffect(() => {
    if (!version || !version.data) return;

    // Construct a stable identity key for the current context
    // If it's a live workspace, use node_id. If history, use version_id.
    const newContextId = version.is_live || version.version_index === -1
      ? `LIVE-${version.node_id}` // Same Node = Same Context for Live
      : `HIST-${version.id}`;     // Different Version ID = New Context

    const isContextSwitch = newContextId !== contextIdRef.current;
    const isDirty = methods.formState.isDirty;

    // [CRITICAL FIX] Intelligent Reset Logic
    // We only force a reset if:
    // 1. User navigated to a completely different context (Node/Version switch)
    // 2. OR The form is pristine (not dirty) - safe to update with latest server data
    //
    // If user is editing (Dirty) and we just received a background refresh (same context),
    // we MUST NOT reset, otherwise we overwrite their work with potentially stale server data.
    
    if (isContextSwitch || !isDirty) {
        const newData = hydrateFormFromABP(version.data);
        
        // Reset form to new baseline
        methods.reset(newData);
        
        // Update reference
        contextIdRef.current = newContextId;
        
        // Log for debugging
        if (isContextSwitch) {
            // console.log(`[StageFormWrapper] Context switch to ${newContextId}. Form Reset.`);
        } else {
            // console.log(`[StageFormWrapper] Background update synced (Pristine).`);
        }
    } else {
        // console.log(`[StageFormWrapper] Update ignored to protect dirty state (Context: ${contextIdRef.current}).`);
    }

  }, [version, methods]); // Dependencies can remain broad as logic handles filtering

  return (
    <FormProvider {...methods}>
      <form className="contents" onSubmit={(e) => e.preventDefault()} autoComplete="off">
        {children}
      </form>
    </FormProvider>
  );
}
