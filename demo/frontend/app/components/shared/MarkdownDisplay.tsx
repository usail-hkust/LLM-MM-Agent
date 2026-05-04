"use client";
import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { cn } from "@/lib/utils";
import { useBlobUrl } from "@/app/hooks/useBlobUrl";
import { Loader2, ImageOff } from "lucide-react";
import "katex/dist/katex.min.css";

const SecureImage = ({ src, alt }: any) => {
  // [FIX] Asset Identification Logic
  // 1. External: http://, https://
  // 2. Inline: data:, blob:
  // 3. Project Asset: Everything else (e.g. "history/...", "img/...", "/api/...")
  const isExternal = src && (src.startsWith("http") || src.startsWith("data:") || src.startsWith("blob:"));

  const { url, loading, error } = useBlobUrl(
    isExternal ? null : src,
    undefined,
    "image/png"
  );

  if (isExternal) {
    return <img src={src} alt={alt} className="rounded-lg my-2 max-w-full shadow-sm" />;
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-4 bg-slate-50 rounded text-xs text-slate-400 border border-slate-100">
        <Loader2 className="animate-spin w-3 h-3" /> Loading asset...
      </div>
    );
  }

  if (error || !url) {
    return (
      <div className="flex items-center gap-2 p-2 bg-red-50 rounded text-xs text-red-400">
        <ImageOff className="w-3 h-3" /> Failed to load
      </div>
    );
  }

  return <img src={url} alt={alt} className="rounded-lg my-2 max-w-full shadow-sm" />;
};

export function MarkdownDisplay({ content, className, isStreaming }: any) {
  // [FIX] Memoize components to prevent remounting and flickering during stream updates
  const components = useMemo(() => ({
    img: SecureImage,
    code: ({node, className, children, ...props}: any) => {
       const match = /language-(\w+)/.exec(className || "");
       return match ? <div className="bg-slate-900 rounded-lg overflow-hidden my-2"><div className="px-3 py-1 text-[10px] text-slate-400 bg-white/5 uppercase font-mono">{match[1]}</div><pre className="!bg-transparent !m-0 !p-3 !rounded-none"><code className={className} {...props}>{children}</code></pre></div> : <code className="bg-slate-100 px-1 py-0.5 rounded text-slate-800 font-mono text-[0.9em]" {...props}>{children}</code>;
    }
  }), []);

  return (
    <div className={cn("prose prose-sm max-w-none dark:prose-invert", className)}>
      <ReactMarkdown 
        remarkPlugins={[remarkGfm, remarkMath]} 
        rehypePlugins={[rehypeKatex]} 
        components={components}
      >
        {content}
      </ReactMarkdown>
      {isStreaming && <span className="inline-block w-1.5 h-4 ml-1 align-middle bg-blue-500 animate-pulse"/>}
    </div>
  );
}
