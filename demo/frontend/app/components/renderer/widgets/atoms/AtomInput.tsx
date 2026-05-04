"use client";
import React, { useRef, useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import TextareaAutosize from "react-textarea-autosize";
import { useBlockDraft } from "@/app/hooks/useBlockDraft";
import { ContentBlock } from "@/app/api/schemas";

export function AtomInput({ block, isReadOnly }: { block: ContentBlock, isReadOnly: boolean }) {
  const { value, onChange } = useBlockDraft(block, isReadOnly);
  const { placeholder, multiline, fillHeight } = block.meta || {};

  // [FIX] 初始化逻辑：仅当 value 确认为非空对象时，才启用对象模式 (影响字体等样式)
  const isObjectPayload = typeof value === 'object' && value !== null;
  const [isObjectMode, setIsObjectMode] = useState(isObjectPayload);

  // [FIX] 本地 Buffer：作为 UI 显示的单一真实数据源 (Single Source of Truth)
  const [localValue, setLocalValue] = useState<string>(() => {
     if (isObjectPayload) return JSON.stringify(value, null, 2);
     return String(value || "");
  });

  const isFocusedRef = useRef(false);

  // [FIX] 外部状态同步守卫
  // 仅当组件【未聚焦】且【外部值与本地不一致】时才同步
  // 这解决了 "输入 -> 自动保存 -> 外部格式化 -> 回填 -> 光标重置" 的核心痛点
  useEffect(() => {
    if (!isFocusedRef.current) {
      const nextDisplay = (typeof value === 'object' && value !== null)
        ? JSON.stringify(value, null, 2)
        : String(value || "");
      
      // 避免不必要的重渲染
      setLocalValue(prev => prev !== nextDisplay ? nextDisplay : prev);
      
      // 如果外部数据突然变为对象（例如后端处理完或 Reset 后），同步更新模式
      if (typeof value === 'object' && value !== null) setIsObjectMode(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const rawInput = e.target.value;
    setLocalValue(rawInput); // 立即更新 UI，保证跟手

    // [CRITICAL FIX] 输入过程中始终提交字符串
    // 即使是对象模式，也不要在 keystroke 阶段尝试 parse。
    // 1. 避免用户无法输入 "{" 等起始字符。
    // 2. 避免 React Hook Form 的 isDirty 判断在 Object/String 之间反复跳变。
    onChange(rawInput);
  };

  // [FIX] 仅在 Blur (失去焦点) 时执行 "解析 -> 格式化 -> 类型升级"
  const handleBlur = () => {
    isFocusedRef.current = false;
    
    // 如果处于对象模式，或者用户输入了类似 JSON 的结构，尝试解析
    const trimmed = localValue.trim();
    if (isObjectMode || trimmed.startsWith("{") || trimmed.startsWith("[")) {
      try {
        const parsed = JSON.parse(trimmed);
        // 1. 向上层提交清洗后的 Object (数据层更新)
        onChange(parsed);
        // 2. 本地美化显示 (视图层更新)
        setLocalValue(JSON.stringify(parsed, null, 2));
        setIsObjectMode(true); 
      } catch {
        // 解析失败：保持原样（字符串状态），不报错，允许用户保存临时草稿
      }
    }
  };

  const handleFocus = () => {
    isFocusedRef.current = true;
  };

  const isMultiline = multiline || isObjectMode;

  return (
    <div className={cn("w-full transition-all", fillHeight ? "h-full flex flex-col" : "relative")}>
      {isMultiline ? (
        <TextareaAutosize
          value={localValue}
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          disabled={isReadOnly}
          placeholder={placeholder}
          minRows={fillHeight ? undefined : 3}
          className={cn(
            "w-full p-3 text-sm font-mono resize-none outline-none bg-transparent text-slate-700 leading-relaxed",
            !isReadOnly && "border border-slate-200 rounded-lg focus:border-blue-400 focus:ring-1 focus:ring-blue-100",
            fillHeight && "flex-1",
            // 智能样式：如果是对象模式，强制使用等宽字体和小字号
            isObjectMode && "font-mono text-xs"
          )}
        />
      ) : (
        <input
          value={localValue}
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          disabled={isReadOnly}
          placeholder={placeholder}
          className={cn(
            "w-full h-10 px-3 text-sm outline-none bg-transparent text-slate-800 font-mono",
            !isReadOnly && "border border-slate-200 rounded-lg focus:border-blue-400 focus:ring-1 focus:ring-blue-100"
          )}
        />
      )}
    </div>
  );
}
