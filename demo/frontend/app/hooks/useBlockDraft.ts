"use client";
import { useState, useEffect, useRef } from "react";
import { useFormContext, useController } from "react-hook-form";
import { useSubmitInteraction } from "@/app/lib/queries";
import { useNodeContext } from "@/app/context/NodeContext";
import { useDebounce } from "@/app/hooks/useDebounce";
import { resolveBindingKey } from "@/app/domain/abp";
import { ContentBlock } from "@/app/api/schemas";

export function useBlockDraft<T = any>(block: ContentBlock, isReadOnly: boolean) {
  const { projectId, nodeId } = useNodeContext();
  const formContext = useFormContext();
  const submit = useSubmitInteraction(projectId, nodeId);
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");

  // 1. 生命周期守卫
  const isMounted = useRef(true);
  useEffect(() => {
    isMounted.current = true;
    return () => { isMounted.current = false; };
  }, []);

  // [FIX] 使用相同的 Key 策略，确保 autosave 更新的是同一个 form field
  const key = resolveBindingKey(block);
  const bindingName = key ? `new_content.${key}` : `temp.${block.id}`;

  const { field, fieldState } = useController({
    name: bindingName,
    control: formContext?.control,
    defaultValue: block.content,
    disabled: isReadOnly || !formContext?.control
  });

  const debounced = useDebounce(field.value, 1000);
  const lastSaved = useRef<T>(block.content as T);

  // 防止跨节点状态竞争
  const currentBlockId = useRef(block.id);
  useEffect(() => { currentBlockId.current = block.id; }, [block.id]);

  // [CRITICAL FIX] Smart Sync Policy: Client Sovereignty
  // Instead of blindly accepting server updates when not "saving", 
  // we strictly check the Dirty State (User Edits).
  useEffect(() => {
    if (block.content !== undefined) {
      const serverVal = JSON.stringify(block.content);
      const localVal = JSON.stringify(field.value);

      if (serverVal !== localVal) {
        // CASE A: Conflict (Server != Local)
        // Only accept override if:
        // 1. Form is NOT dirty (User hasn't touched it since last confirmed save)
        // 2. We are NOT currently saving (Optimistic update protection)
        if (!fieldState.isDirty && status !== "saving") {
           // console.log(`[Sync] Accepting backend update for ${block.id}`);
           field.onChange(block.content);
           lastSaved.current = block.content as T;
           
           // Force reset baseline to prevent "Phantom Dirty" state
           // where value matches but RHF thinks it differs from old default
           formContext.resetField(bindingName, { 
              defaultValue: block.content,
              keepDirty: false,
              keepTouched: false
           });
        } else {
           // console.log(`[Sync] Rejected backend update for ${block.id} (Dirty: ${fieldState.isDirty}, Status: ${status})`);
        }
      } else {
        // CASE B: Match (Server == Local)
        // Server has confirmed our latest save. 
        // We can now safely clear the Dirty flag by resetting the baseline.
        if (fieldState.isDirty) {
           // console.log(`[Sync] Server confirmed save for ${block.id}. Clearing dirty flag.`);
           formContext.resetField(bindingName, { 
              defaultValue: block.content,
              keepDirty: false 
           });
        }
      }
    }
  }, [block.content]); // Trigger only when backend data arrives

  useEffect(() => {
    // 基础守卫
    if (isReadOnly || !nodeId) return;

    // 检查实际变更
    const hasChanged = JSON.stringify(debounced) !== JSON.stringify(lastSaved.current);
    if (!hasChanged) return;

    const activeId = currentBlockId.current;

    setStatus("saving");
    submit.mutateAsync({
      action: "save_draft",
      payload: { block_id: activeId, content: debounced }
    })
      .then(() => {
        // 仅当组件仍在挂载且 Block ID 未变时更新
        if (isMounted.current && currentBlockId.current === activeId) {
          lastSaved.current = debounced;
          setStatus("saved");

          // Note: We do NOT resetField here anymore.
          // We wait for the Server to echo back the new value in the next Poll/Push.
          // This ensures `isDirty` acts as a "Lock" until consistency is proven.

          setTimeout(() => {
            if (isMounted.current && currentBlockId.current === activeId) {
              setStatus(s => s === "saved" ? "idle" : s);
            }
          }, 2000);
        }
      })
      .catch(() => {
        if (isMounted.current && currentBlockId.current === activeId) {
          setStatus("error");
        }
      });
  }, [debounced, nodeId, projectId, isReadOnly, submit]);

  return { ...field, status };
}
