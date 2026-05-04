"use client";
import { AtomShell } from "./AtomShell";
import { ExternalLink, Image as ImageIcon, FileJson, Loader2, FileText, BarChart } from "lucide-react";
import { useBlobUrl } from "@/app/hooks/useBlobUrl";
import { RenderAtomProps } from "@/app/domain/abp";
import { cn } from "@/lib/utils";

// [FIX] Source Resolution Strategy with Context
function getArtifactSource(artifact: any) {
  // 1. CAS Hash (Fastest, Immutable)
  if (artifact.blobHash || artifact.meta?.blob_hash) {
    return { 
        blob_hash: artifact.blobHash || artifact.meta.blob_hash,
        // [FIX] Pass filename hint to useBlobUrl for query parameter injection
        filename: artifact.label || artifact.meta?.filename || artifact.name
    };
  }
  // 2. Virtual/Remote Path
  if (artifact.meta?.virtual_path || artifact.meta?.remote_path) {
    return { remote_path: artifact.meta.virtual_path || artifact.meta.remote_path };
  }
  // 3. Direct URL (Legacy)
  if (artifact.url || artifact.meta?.url) return artifact.url || artifact.meta.url;

  // 4. Inline Data
  if (artifact.data || artifact.content) return artifact.data || artifact.content;

  return null;
}

const ArtifactItem = ({ item }: { item: any }) => {
  const source = getArtifactSource(item);
  const type = item.meta?.mime_type || item.type || "application/octet-stream";
  const name = item.label || item.meta?.filename || item.name || "Artifact";

  const { url, loading, error } = useBlobUrl(source, undefined, type);

  // Heuristic for image type
  const isImg = type.startsWith("image/") || name.match(/\.(jpg|png|webp|svg)$/i);

  return (
    <div className="group relative border rounded-xl bg-white overflow-hidden aspect-square flex flex-col items-center justify-center hover:shadow-md transition-all">
      {loading ? (
        <Loader2 className="animate-spin text-slate-400 w-5 h-5" />
      ) : error ? (
        <div className="text-xs text-red-400 p-2 text-center break-words w-full">Failed to load</div>
      ) : isImg && url ? (
        <img src={url} alt={name} className="absolute inset-0 w-full h-full object-contain bg-slate-50/30 p-2" />
      ) : (
        <div className="flex flex-col items-center gap-2 text-slate-500 p-2">
          <FileText className="w-8 h-8" />
          <span className="text-[10px] px-1 text-center line-clamp-2 leading-tight">{name}</span>
        </div>
      )}

      {/* Overlay Actions */}
      <div className="absolute inset-x-0 bottom-0 bg-white/95 border-t p-2 text-xs flex justify-between items-center translate-y-full group-hover:translate-y-0 transition-transform z-10">
        <span className="truncate max-w-[80px]">{name}</span>
        {url && (
          <a
            href={url}
            download={name}
            className="text-blue-600 hover:bg-blue-50 p-1 rounded"
            onClick={(e) => e.stopPropagation()}
          >
            <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>
    </div>
  );
};

export function AtomArtifacts(props: RenderAtomProps) {
  const { block } = props;

  let items: any[] = [];
  if (Array.isArray(block.content)) {
    items = block.content;
  } else if (block.content) {
    items = [{ data: block.content, meta: block.meta, label: block.label }];
  } else if (block.meta?.blob_hash || block.meta?.url || block.meta?.virtual_path) {
    items = [{ content: null, meta: block.meta, label: block.label }];
  }

  if (items.length === 0) return null;

  return (
    <AtomShell {...props} label="Artifacts" icon={ImageIcon}>
      <div
        className={cn(
          "p-4 bg-slate-50/50 rounded-lg",
          items.length > 1 ? "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4" : "flex justify-center"
        )}
      >
        {items.map((it: any, i: number) => (
          <div key={i} className={cn(items.length === 1 && "w-full max-w-sm")}>
            <ArtifactItem item={it} />
          </div>
        ))}
      </div>
    </AtomShell>
  );
}
