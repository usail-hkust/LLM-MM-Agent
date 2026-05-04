"use client";

import { useState } from "react";
import { useAuth } from "@/app/context/AuthContext";
import { useUI } from "@/app/hooks/useUI";

export function useProjectExport() {
  const [isExporting, setIsExporting] = useState(false);
  const { token } = useAuth();
  const { toast } = useUI();

  const triggerExport = async (projectId: string) => {
    if (!token) {
      toast.error("You must be logged in to export projects.");
      return;
    }

    setIsExporting(true);
    // Optional: Inform user if download might take a while
    // toast.info("Preparing export archive...");

    try {
      const root = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";
      // Ensure no trailing slash for clean concatenation
      const cleanRoot = root.replace(/\/$/, ""); 
      
      const response = await fetch(`${cleanRoot}/projects/${projectId}/export`, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });

      if (!response.ok) {
        if (response.status === 404) throw new Error("Project not found.");
        if (response.status === 403) throw new Error("Permission denied.");
        throw new Error("Export failed on server.");
      }

      // --- Filename Extraction Strategy ---
      const disposition = response.headers.get("Content-Disposition");
      let filename = `project_${projectId}_export.zip`;
      
      if (disposition) {
        // Priority 1: RFC 5987 (UTF-8)
        // Example: filename*=UTF-8''My%20Project.zip
        const utf8Match = /filename\*=UTF-8''([^;]+)/.exec(disposition);
        if (utf8Match && utf8Match[1]) {
          filename = decodeURIComponent(utf8Match[1]);
        } 
        // Priority 2: Standard filename
        // Example: filename="My Project.zip"
        else {
          const stdMatch = /filename="?([^";]+)"?/.exec(disposition);
          if (stdMatch && stdMatch[1]) {
            filename = stdMatch[1];
          }
        }
      }

      // --- Blob Handling ---
      const blob = await response.blob();
      
      // Create transient link to trigger download
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      
      // Cleanup
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast.success("Export downloaded successfully");
    } catch (error: any) {
      console.error("[Export Error]", error);
      toast.error(error.message || "Failed to download export archive");
    } finally {
      setIsExporting(false);
    }
  };

  return { triggerExport, isExporting };
}
