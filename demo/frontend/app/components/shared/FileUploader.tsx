"use client";

import { useCallback, useState } from "react";
import { cn } from "@/lib/utils";
import { UploadCloud, FileText, FileSpreadsheet, X, File as FileIcon } from "lucide-react";

interface FileUploaderProps {
  files: File[];
  onFilesChange: (files: File[]) => void;
}

export function FileUploader({ files, onFilesChange }: FileUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const droppedFiles = Array.from(e.dataTransfer.files);
      // Filter: prohibit images and zip files
      const prohibitedPattern = /\.(png|jpg|jpeg|gif|bmp|webp|svg|ico|tiff|tif|heic|heif|zip|rar|7z|tar|gz|bz2|xz)$/i;
      const allowed = droppedFiles.filter(f => {
        if (prohibitedPattern.test(f.name)) {
          return false;
        }
        return true;
      });
      if (allowed.length > 0) {
        onFilesChange([...files, ...allowed]);
      } else if (droppedFiles.length > 0) {
        // Show error if all files were rejected
        alert("不支持上传图片和压缩文件");
      }
    },
    [files, onFilesChange]
  );

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selected = Array.from(e.target.files);
      // Filter: prohibit images and zip files
      const prohibitedPattern = /\.(png|jpg|jpeg|gif|bmp|webp|svg|ico|tiff|tif|heic|heif|zip|rar|7z|tar|gz|bz2|xz)$/i;
      const allowed = selected.filter(f => !prohibitedPattern.test(f.name));
      if (allowed.length > 0) {
        onFilesChange([...files, ...allowed]);
      }
      if (allowed.length < selected.length) {
        alert("不支持上传图片和压缩文件");
      }
    }
  };

  const removeFile = (index: number) => {
    const newFiles = [...files];
    newFiles.splice(index, 1);
    onFilesChange(newFiles);
  };

  const getIcon = (name: string) => {
    if (name.endsWith(".pdf")) return <FileText className="w-5 h-5 text-red-500" />;
    if (name.match(/\.(xlsx|csv)$/)) return <FileSpreadsheet className="w-5 h-5 text-green-500" />;
    return <FileIcon className="w-5 h-5 text-slate-400" />;
  };

  return (
    <div className="space-y-4">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          "border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center transition-all cursor-pointer text-center",
          isDragging
            ? "border-blue-500 bg-blue-50"
            : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
        )}
      >
        <label className="cursor-pointer w-full h-full flex flex-col items-center">
          <UploadCloud
            className={cn(
              "w-10 h-10 mb-3",
              isDragging ? "text-blue-500" : "text-slate-300"
            )}
          />
          <span className="text-sm font-bold text-slate-700">
            Click to upload or drag & drop
          </span>
          <span className="text-xs text-slate-400 mt-1">
            PDF, Excel, CSV, TXT 等文件 (不支持图片和压缩文件，Max 50MB)
          </span>
          <input
            type="file"
            multiple
            className="hidden"
            accept=".pdf,.csv,.xlsx,.txt"
            onChange={handleFileInput}
          />
        </label>
      </div>

      {files.length > 0 && (
        <div className="grid grid-cols-1 gap-2">
          {files.map((file, idx) => (
            <div
              key={`${file.name}-${idx}`}
              className="flex items-center justify-between p-3 bg-white border border-slate-100 rounded-lg shadow-sm animate-in fade-in slide-in-from-top-1"
            >
              <div className="flex items-center gap-3 overflow-hidden">
                {getIcon(file.name)}
                <div className="flex flex-col min-w-0 text-left">
                  <span className="text-sm font-medium text-slate-700 truncate">
                    {file.name}
                  </span>
                  <span className="text-[10px] text-slate-400">
                    {(file.size / 1024).toFixed(1)} KB
                  </span>
                </div>
              </div>
              <button
                onClick={() => removeFile(idx)}
                className="p-1.5 hover:bg-red-50 text-slate-400 hover:text-red-500 rounded-md transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}





