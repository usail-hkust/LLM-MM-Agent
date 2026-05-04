"use client";

import React, { useState, useMemo, useEffect } from "react";
import { 
  FileText, 
  ImageIcon, 
  FileCode, 
  ChevronRight, 
  ChevronDown, 
  Lock,
  LayoutTemplate,
  File
} from "lucide-react";
import { cn } from "@/lib/utils";
import { RenderAtomProps } from "@/app/domain/abp";
import { useAtomBinding } from "@/app/hooks/useAtomBinding";
import { AtomShell } from "../atoms/AtomShell";
import { PureCodeEditor } from "@/app/components/stage/pure/PureCodeEditor";
import { useBlobUrl } from "@/app/hooks/useBlobUrl";

// --- Types Definition based on Backend Contract ---

interface FileEntry {
  type: "LATEX_MAIN" | "LATEX_PART" | "STYLE" | "ASSET" | "BUILD_LOG" | "PDF_OUTPUT" | "SCRIPT";
  content?: string;
  blob_hash?: string;
  readonly?: boolean;
}

interface WorkspaceState {
  [path: string]: FileEntry;
}

// --- Helper Components ---

const FileIcon = ({ name, type }: { name: string; type: string }) => {
  if (type === "ASSET" || name.match(/\.(png|jpg|jpeg|svg)$/i)) return <ImageIcon className="w-3.5 h-3.5 text-purple-500" />;
  if (type === "PDF_OUTPUT" || name.endsWith(".pdf")) return <FileText className="w-3.5 h-3.5 text-red-500" />;
  if (name.endsWith(".tex")) return <FileText className="w-3.5 h-3.5 text-blue-500" />;
  if (name.endsWith(".sty") || name.endsWith(".cls")) return <LayoutTemplate className="w-3.5 h-3.5 text-slate-500" />;
  if (name.endsWith(".py")) return <FileCode className="w-3.5 h-3.5 text-amber-500" />;
  if (name.endsWith(".json")) return <FileCode className="w-3.5 h-3.5 text-yellow-500" />;
  return <File className="w-3.5 h-3.5 text-slate-400" />;
};

const ImagePreview = ({ entry, name }: { entry: FileEntry; name: string }) => {
  // Construct source object for useBlobUrl
  const source = entry.blob_hash 
    ? { blob_hash: entry.blob_hash } 
    : (entry.content ? entry.content : null); // Fallback for inline base64 if supported later

  // Determine mime type hint
  const mime = name.endsWith(".pdf") ? "application/pdf" : "image/png";
  
  const { url, loading, error } = useBlobUrl(source, undefined, mime);

  if (loading) return (
    <div className="flex flex-col items-center justify-center h-full text-slate-400 text-xs gap-2">
      <div className="w-6 h-6 border-2 border-slate-200 border-t-blue-500 rounded-full animate-spin" />
      <span>Loading asset...</span>
    </div>
  );
  
  if (error || !url) return (
    <div className="flex flex-col items-center justify-center h-full text-red-400 text-xs gap-2 bg-red-50/50 m-4 rounded-lg border border-red-100">
      <span>Failed to load asset</span>
      <span className="opacity-50 text-[10px]">{error || "Unknown error"}</span>
    </div>
  );
  
  if (name.endsWith(".pdf")) {
      return <iframe src={url} className="w-full h-full border-none bg-slate-100" title={name} />;
  }
  
  return (
    <div className="flex items-center justify-center h-full bg-slate-100/50 p-8 overflow-auto">
      <img src={url} alt={name} className="max-w-full max-h-full object-contain shadow-sm border border-slate-200 rounded bg-white" />
    </div>
  );
};

// --- Main Component ---

export const EntityIdeWorkspace: React.FC<RenderAtomProps> = (props) => {
  const { block } = props;
  // Two-way binding for the entire workspace state (File Tree)
  const { value, onChange, isReadOnly: globalReadOnly } = useAtomBinding<WorkspaceState>(props);
  
  // Safe unwrap: value takes precedence (edit state), block.content is initial
  const workspace = (value || block.content || {}) as WorkspaceState;
  
  // --- UI State ---
  const [activePath, setActivePath] = useState<string | null>(null);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set(["sections", "img"]));

  // Auto-select main.tex or reasonable default on mount
  useEffect(() => {
    if (!activePath && Object.keys(workspace).length > 0) {
      if (workspace["main.tex"]) setActivePath("main.tex");
      else if (workspace["sections/00_abstract.tex"]) setActivePath("sections/00_abstract.tex");
      else {
        // Fallback: pick first non-binary file if possible
        const first = Object.keys(workspace).find(k => !k.startsWith("img/") && k.endsWith(".tex")) || Object.keys(workspace)[0];
        setActivePath(first);
      }
    }
  }, [workspace, activePath]);

  // Transform flat path map to nested tree structure for rendering
  const fileTree = useMemo(() => {
    const tree: Record<string, any> = {};
    const paths = Object.keys(workspace).sort(); // Alphabetical sort
    
    paths.forEach(path => {
      const parts = path.split("/");
      let current = tree;
      parts.forEach((part, i) => {
        if (i === parts.length - 1) {
          // Leaf node (File)
          current[part] = { _is_file: true, path, ...workspace[path] };
        } else {
          // Branch node (Folder)
          current[part] = current[part] || {};
          current = current[part];
        }
      });
    });
    return tree;
  }, [workspace]);

  const toggleFolder = (folderName: string) => {
    const next = new Set(expandedFolders);
    if (next.has(folderName)) next.delete(folderName);
    else next.add(folderName);
    setExpandedFolders(next);
  };

  const handleFileChange = (newContent: string) => {
    if (!activePath || globalReadOnly) return;
    
    const entry = workspace[activePath];
    // Guard: Don't edit readonly files or binary files
    if (entry.readonly || entry.type === "ASSET" || entry.type === "PDF_OUTPUT") return;

    // Immutable update of the workspace tree
    const newWorkspace = {
      ...workspace,
      [activePath]: {
        ...entry,
        content: newContent
      }
    };
    
    onChange(newWorkspace);
  };

  // --- Recursive Tree Renderer ---
  const renderTree = (node: any, depth = 0, parentPath = "") => {
    // Separate folders and files for sorting (Folders first)
    const entries = Object.entries(node);
    const folders = entries.filter(([_, v]: [string, any]) => !v._is_file);
    const files = entries.filter(([_, v]: [string, any]) => v._is_file);
    
    // Sort logic: Folders A-Z, then Files A-Z
    const sortedEntries = [...folders, ...files];

    return sortedEntries.map(([name, data]: [string, any]) => {
      if (data._is_file) {
        const isActive = data.path === activePath;
        return (
          <div 
            key={data.path}
            onClick={() => setActivePath(data.path)}
            className={cn(
              "flex items-center gap-2 px-3 py-1.5 cursor-pointer text-xs transition-all border-l-2 select-none group",
              isActive 
                ? "bg-blue-50 border-blue-500 text-blue-700 font-medium" 
                : "border-transparent text-slate-600 hover:bg-slate-50 hover:text-slate-900"
            )}
            style={{ paddingLeft: `${depth * 12 + 12}px` }}
          >
            <FileIcon name={name} type={data.type} />
            <span className="truncate flex-1">{name}</span>
            {data.readonly && <Lock className="w-2.5 h-2.5 ml-2 text-slate-300 group-hover:text-slate-400" />}
          </div>
        );
      } else {
        const fullPath = parentPath ? `${parentPath}/${name}` : name;
        const isExpanded = expandedFolders.has(name) || expandedFolders.has(fullPath);
        return (
          <div key={fullPath}>
            <div 
              onClick={() => toggleFolder(name)}
              className="flex items-center gap-1.5 px-3 py-1.5 cursor-pointer text-xs font-bold text-slate-500 hover:text-slate-700 select-none hover:bg-slate-50/50"
              style={{ paddingLeft: `${depth * 12 + 8}px` }}
            >
              {isExpanded ? <ChevronDown className="w-3 h-3"/> : <ChevronRight className="w-3 h-3"/>}
              <span className="truncate">{name}</span>
            </div>
            {isExpanded && renderTree(data, depth + 1, fullPath)}
          </div>
        );
      }
    });
  };

  const activeEntry = activePath ? workspace[activePath] : null;
  const isBinary = activeEntry?.type === "ASSET" || activeEntry?.type === "PDF_OUTPUT";
  const activeLang = activePath?.endsWith(".py") ? "python" : "latex";

  return (
    <AtomShell {...props} variant="default" label="Paper Writing" hideHeader>
      {() => (
        <div className="flex flex-col h-[650px] border border-slate-200 rounded-xl overflow-hidden bg-white shadow-sm">
          
          {/* Header Bar */}
          <div className="h-10 bg-slate-50 border-b border-slate-200 flex items-center justify-between px-4 shrink-0">
             <span className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-2">
               <LayoutTemplate className="w-3.5 h-3.5" /> Workspace
             </span>
             {globalReadOnly && (
                <span className="text-[10px] bg-slate-200 text-slate-500 px-2 py-0.5 rounded-full font-bold">
                  READ ONLY
                </span>
             )}
          </div>

          <div className="flex flex-1 min-h-0">
            {/* Left: File Explorer */}
            <div className="w-60 flex flex-col border-r border-slate-200 bg-slate-50/30">
              <div className="px-4 py-2 border-b border-slate-100 bg-white/50">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Explorer</span>
              </div>
              <div className="flex-1 overflow-y-auto py-2 custom-scrollbar">
                {renderTree(fileTree)}
              </div>
            </div>

            {/* Right: Editor / Preview Area */}
            <div className="flex-1 flex flex-col min-w-0 bg-white relative">
              {/* Tab Header */}
              <div className="h-9 border-b border-slate-200 flex items-center bg-slate-50/50 px-2 gap-1 overflow-x-auto no-scrollbar">
                  {activePath ? (
                      <div className="flex items-center gap-2 px-3 py-1.5 bg-white border border-slate-200 border-b-0 rounded-t-md shadow-sm text-xs font-medium text-slate-700 relative top-[1px] select-none">
                          <FileIcon name={activePath} type={activeEntry?.type || ""} />
                          <span className="max-w-[150px] truncate">{activePath}</span>
                          {activeEntry?.readonly && <Lock className="w-3 h-3 text-slate-300 ml-1" />}
                      </div>
                  ) : (
                    <div className="px-3 py-1.5 text-xs text-slate-400 italic select-none">No file selected</div>
                  )}
              </div>

              {/* Editor Body */}
              <div className="flex-1 relative overflow-hidden">
                  {!activeEntry ? (
                      <div className="flex items-center justify-center h-full text-slate-300 text-sm gap-2 select-none">
                          <FileText className="w-8 h-8 opacity-50" />
                          <span>Select a file to view or edit</span>
                      </div>
                  ) : isBinary ? (
                      <ImagePreview entry={activeEntry} name={activePath!} />
                  ) : (
                      <PureCodeEditor
                          value={activeEntry.content || ""}
                          language={activeLang}
                          readOnly={globalReadOnly || !!activeEntry.readonly}
                          onChange={handleFileChange}
                          className="h-full"
                          paddingBottom={16} 
                      />
                  )}
              </div>
            </div>
          </div>
        </div>
      )}
    </AtomShell>
  );
};
