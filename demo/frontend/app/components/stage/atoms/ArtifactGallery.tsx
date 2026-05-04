"use client";

import { useState, useEffect, useMemo } from "react";
import { createPortal } from "react-dom";
import { X, Image as ImageIcon, FileJson, Download, BarChart3, FileText, Loader2 } from "lucide-react";
import { ExecutionArtifact } from "@/app/lib/api-types";
import { motion, AnimatePresence } from "framer-motion";
import { useBlobUrl } from "@/app/hooks/useBlobUrl";
import { cn } from "@/lib/utils";

interface ArtifactGalleryProps {
  artifacts: ExecutionArtifact[];
}

/**
 * [HELPER] Construct a robust source object for useBlobUrl Hook.
 * Priority: URL > Inline Data > Blob Hash (CAS)
 */
function getArtifactSource(artifact: ExecutionArtifact) {
  if (typeof artifact.url === "string" && artifact.url) return artifact.url;
  if (typeof artifact.data === "string" && artifact.data) return artifact.data;
  if (artifact.blobHash) {
    return {
      blob_hash: artifact.blobHash,
      // [FIX] Pass filename to enable backend query param injection
      filename: artifact.name
    };
  }
  return null;
}

/**
 * [NEW] Dedicated Download Button Component
 * Handles fetching the blob and triggering a browser download.
 */
const ArtifactDownloadButton = ({ artifact, className, showLabel = false }: { artifact: ExecutionArtifact, className?: string, showLabel?: boolean }) => {
  const source = useMemo(() => getArtifactSource(artifact), [artifact]);
  const { url, loading, error } = useBlobUrl(source, undefined, artifact.type);

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!url) return;
    const a = document.createElement("a");
    a.href = url;
    a.download = artifact.name || "download";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  if (error) return null;

  return (
    <button
      onClick={handleDownload}
      disabled={loading || !url}
      className={cn(
        "flex items-center justify-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
        className
      )}
      title="Download Artifact"
    >
      {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
      {showLabel && <span className="text-xs font-bold">Download</span>}
    </button>
  );
};

// [NEW] Text content previewer for non-images
const ArtifactText = ({ artifact }: { artifact: ExecutionArtifact }) => {
  const source = useMemo(() => getArtifactSource(artifact), [artifact]);
  const { url, loading, error } = useBlobUrl(source, undefined, artifact.type);
  const [content, setContent] = useState<string | null>(null);
  const [fetching, setFetching] = useState(false);

  useEffect(() => {
    if (url && !artifact.data && !content) {
      setFetching(true);
      fetch(url)
        .then(res => res.text())
        .then(text => setContent(text))
        .catch(err => console.error("Failed to fetch artifact text:", err))
        .finally(() => setFetching(false));
    }
  }, [url, artifact.data, content]);

  const displayContent = artifact.data || content;

  if (loading || fetching) return (
    <div className="flex flex-col items-center justify-center p-12 text-slate-400 gap-3">
      <Loader2 className="w-8 h-8 animate-spin" />
      <span className="text-xs">Loading content...</span>
    </div>
  );

  if (error) return <div className="p-8 text-red-500 text-sm">Failed to load content.</div>;
  if (!displayContent) return <div className="p-8 text-slate-400 text-sm">No content available to preview.</div>;

  return (
    <pre className="w-full text-[11px] font-mono p-4 bg-slate-900 text-slate-300 rounded-lg overflow-auto max-h-[60vh] border border-slate-700 shadow-inner">
      {displayContent}
    </pre>
  );
};

// [UPDATED] Secure Image Loader Component
const ArtifactImage = ({ artifact, className }: { artifact: ExecutionArtifact; className?: string }) => {
  const source = useMemo(() => getArtifactSource(artifact), [artifact]);
  // Use correct MIME type to ensure browser can render it
  const { url, loading, error } = useBlobUrl(source, undefined, artifact.type ?? "image/png");

  if (loading) return <div className="animate-pulse bg-slate-100 w-full h-full rounded flex items-center justify-center"><Loader2 className="w-4 h-4 animate-spin text-slate-300" /></div>;
  if (error) return <div className="bg-red-50 text-red-400 w-full h-full flex items-center justify-center text-[10px] p-2 text-center">Preview Error</div>;
  if (!url) return <div className="bg-slate-100 w-full h-full flex items-center justify-center text-slate-300 text-[10px]">No Data</div>;

  return <img src={url} alt={artifact.name} className={className} />;
};

export function ArtifactGallery({ artifacts }: ArtifactGalleryProps) {
  const [selectedArtifact, setSelectedArtifact] = useState<ExecutionArtifact | null>(null);

  if (!artifacts || artifacts.length === 0) return null;

  return (
    <>
      {/* [CSS] Use auto-fill with minmax(120px) for responsive grid */}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(140px,1fr))] gap-3 content-start">
        {artifacts.map((art, index) => {
          const key = art.id ?? art.blobHash ?? `${art.name}-${index}`;
          return <ArtifactCard key={key} artifact={art} onClick={() => setSelectedArtifact(art)} />;
        })}
      </div>

      <Lightbox artifact={selectedArtifact} onClose={() => setSelectedArtifact(null)} />
    </>
  );
}

function ArtifactCard({ artifact, onClick }: { artifact: ExecutionArtifact; onClick: () => void }) {
  const type = artifact.type && typeof artifact.type === 'string' ? artifact.type : "unknown";
  const isImage = type.startsWith("image/");

  let Icon = FileText;
  if (type.includes("json")) Icon = FileJson;
  if (type.includes("chart") || type.includes("csv") || type.includes("spreadsheet")) Icon = BarChart3;
  if (type.includes("image/")) Icon = ImageIcon;

  return (
    <div className="group relative aspect-square bg-white rounded-xl border border-slate-200 shadow-sm hover:shadow-md hover:border-blue-300 transition-all overflow-hidden">
      {/* Main Click Area */}
      <button
        onClick={onClick}
        className="w-full h-full flex flex-col items-center justify-center outline-none"
      >
        {isImage ? (
          <ArtifactImage artifact={artifact} className="w-full h-full object-cover" />
        ) : (
          <div className="flex flex-col items-center gap-2 text-slate-400 group-hover:text-blue-500 p-4 text-center">
            <Icon className="w-8 h-8 transition-colors" />
            <div className="flex flex-col gap-0.5 max-w-full">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 truncate w-full px-2">
                {artifact.name}
              </span>
              <span className="text-[9px] font-mono px-2 truncate w-full bg-slate-50 py-0.5 rounded border border-slate-100 text-slate-400">
                {type !== "unknown" ? type.split("/").pop() : "unknown"}
              </span>
            </div>
          </div>
        )}
      </button>

      {/* [FIX] Overlay Actions - Download Button */}
      <div className="absolute inset-x-0 bottom-0 bg-white/95 backdrop-blur-sm px-3 py-2 border-t border-slate-100 translate-y-full group-hover:translate-y-0 transition-transform duration-200 flex justify-between items-center z-10">
        <span className="text-xs font-medium text-slate-700 truncate flex-1 mr-2" title={artifact.name}>
          {artifact.name}
        </span>
        <ArtifactDownloadButton
          artifact={artifact}
          className="p-1.5 hover:bg-slate-100 rounded-md text-slate-500 hover:text-blue-600"
        />
      </div>
    </div>
  );
}

// Lightbox 组件
function Lightbox({ artifact, onClose }: { artifact: ExecutionArtifact | null; onClose: () => void }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    return () => setMounted(false);
  }, []);

  if (!artifact || !mounted) return null;
  if (typeof document === 'undefined') return null;

  const type = artifact.type && typeof artifact.type === 'string' ? artifact.type : "unknown";
  const isImage = type.startsWith("image/");

  return createPortal(
    <AnimatePresence>
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-slate-900/80 backdrop-blur-sm"
        />

        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          className="bg-white rounded-xl overflow-hidden shadow-2xl max-w-5xl w-full max-h-[90vh] flex flex-col relative z-10"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b bg-white">
            <div className="flex items-center gap-3 overflow-hidden">
              <div className="p-2 bg-slate-100 rounded-lg shrink-0">
                {isImage ? <ImageIcon className="w-5 h-5 text-blue-500" /> : <FileText className="w-5 h-5 text-amber-500" />}
              </div>
              <div className="min-w-0">
                <h3 className="font-bold text-slate-800 text-sm truncate">{artifact.name}</h3>
                <p className="text-xs text-slate-500 font-mono truncate">{type || "unknown"}</p>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {/* [FIX] Download Button in Lightbox */}
              <ArtifactDownloadButton
                artifact={artifact}
                showLabel
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-xs font-bold"
              />
              <div className="w-px h-6 bg-slate-200 mx-2" />
              <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-lg transition-colors text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-auto bg-slate-50 p-8 flex items-center justify-center relative min-h-[300px]">
            {isImage ? (
              <ArtifactImage artifact={artifact} className="max-w-full max-h-full object-contain shadow-lg rounded border border-slate-200" />
            ) : type.includes("text/") || type.includes("json") || type.includes("csv") || type.includes("javascript") || type.includes("python") || type.includes("markdown") ? (
              <div className="w-full max-w-4xl">
                <ArtifactText artifact={artifact} />
              </div>
            ) : (
              // Fallback Viewer for non-previewable files
              <div className="bg-white p-8 rounded-xl shadow-sm border border-slate-200 text-center max-w-md">
                <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Download className="w-8 h-8 text-slate-400" />
                </div>
                <h4 className="text-slate-900 font-bold mb-2">Preview Not Available</h4>
                <p className="text-slate-500 text-xs">
                  This file type ({type}) cannot be previewed directly in the browser.
                  Please download it to view locally.
                </p>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>,
    document.body
  );
}
