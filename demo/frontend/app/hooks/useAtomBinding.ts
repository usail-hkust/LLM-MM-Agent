"use client";
import { useController, useFormContext } from "react-hook-form";
import { RenderAtomProps, resolveBindingKey } from "@/app/domain/abp";
import { useEffect, useRef } from "react";

export function useAtomBinding<T = unknown>(props: RenderAtomProps) {
  const { block, state } = props;
  const formContext = useFormContext();

  // [FIX] 使用统一的 SSoT Key
  const key = resolveBindingKey(block);
  const bindingName = key ? `new_content.${key}` : "";
  
  const shouldBind = !state.read_only && !!formContext && !!bindingName;

  const { field, fieldState } = useController({
    name: bindingName || `noop_${block.id}`, // 防止 name 为空报错
    control: formContext?.control,
    defaultValue: block.content,
    disabled: !shouldBind
  });

  // [FIX: Authoritative Sync Strategy]
  // 核心问题：当组件重新挂载(Remount)时，如果 Block ID 变了但 bindingName(key) 没变，
  // RHF 会保留旧的脏数据（用户输入的 Reject Comment），而 useRef 如果用 block.id 初始化，
  // 会导致 Effect 认为 ID 没变从而跳过重置。
  // 解决方案：使用 null 初始化 prevId，强制在组件挂载时(Mount)执行一次权威性检查。
  const prevId = useRef<string | null>(null);
  const prevContentHash = useRef<string>("");

  useEffect(() => {
      if (shouldBind && bindingName) {
          const currentHash = JSON.stringify(block.content);
          const currentFormValueHash = JSON.stringify(field.value);
          
          // Check 1: ID Mismatch (Mount/Switch)
          const isIdChanged = block.id !== prevId.current;
          
          // Check 2: Content Mismatch (Backend Update)
          const isContentChanged = currentHash !== prevContentHash.current;

          // [CRITICAL FIX 2] Desync Detection (External Reset Reversal)
          // 场景：StageFormWrapper 收到旧的历史数据，强制 reset 了表单(V2)。
          // 但此时 Props (block.content) 依然是新的(V3)。
          // 这时 isIdChanged=false, isContentChanged=false (因为上次已经 sync 过了)。
          // 但 field.value != block.content。且由于是 reset 触发的，isDirty 为 false。
          // 此时必须强制再次同步。
          const isFormDesynced = (currentFormValueHash !== currentHash) && !fieldState.isDirty;

          if (isIdChanged || isContentChanged || isFormDesynced) {
              
              if (currentFormValueHash !== currentHash) {
                   console.log(`[AtomBinding] Hard Sync for ${bindingName}. (Reason: ID=${isIdChanged}, Content=${isContentChanged}, Desync=${isFormDesynced})`);
                   
                   formContext.resetField(bindingName, { 
                      defaultValue: block.content,
                      keepDirty: false, 
                      keepTouched: false,
                      keepError: false
                   });
              }

              prevId.current = block.id;
              prevContentHash.current = currentHash;
          }
      }
  }, [
      block.id, 
      block.content, 
      bindingName, 
      shouldBind, 
      formContext, 
      field.value, 
      fieldState.isDirty // [FIX] Add dependency
  ]);

  if (!shouldBind) {
    return { value: block.content as T, onChange: () => {}, isReadOnly: true, isDirty: false };
  }

  return {
    value: (field.value ?? block.content) as T,
    onChange: field.onChange,
    isReadOnly: false,
    isDirty: fieldState.isDirty
  };
}
