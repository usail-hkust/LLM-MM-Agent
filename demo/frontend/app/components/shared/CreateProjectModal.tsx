"use client";

import { useState } from "react";
import { Loader2, FolderOpen, FileUp, TextCursorInput } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useCreateProject } from "@/app/lib/queries";
import { FileUploader } from "./FileUploader";

interface CreateProjectModalProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: (projectId: string) => void;
}

export function CreateProjectModal({ isOpen, onOpenChange, onSuccess }: CreateProjectModalProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [name, setName] = useState("My Agent Project");
  // [FIX] Provide a default instruction to ensure auto-run
  const [instruction, setInstruction] = useState("Analyze the provided data and generate a comprehensive mathematical model.");
  
  const createMutation = useCreateProject();

  const handleSubmit = async () => {
    if (!name.trim()) return;

    const formData = new FormData();
    formData.append("name", name);
    // [FIX] Ensure instruction is never empty string
    formData.append("instruction", instruction.trim() || "Analyze the problem.");
    files.forEach((f) => formData.append("files", f));

    createMutation.mutate(formData, {
        onSuccess: (data: any) => {
            onOpenChange(false);
            // Reset
            setName("My Agent Project");
            setInstruction("Analyze the provided data and generate a comprehensive mathematical model.");
            setFiles([]);
            onSuccess(data.id);
        }
    });
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Start New Workflow</DialogTitle>
          <DialogDescription>
            Configure the automated agent. The workflow will start immediately upon creation.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-6 py-4">
          {/* Project Name */}
          <div className="grid gap-2">
            <div className="flex items-center gap-2 text-sm font-medium">
                <FolderOpen className="w-4 h-4 text-blue-500" /> Project Name
            </div>
            <Input 
                value={name} 
                onChange={(e) => setName(e.target.value)} 
                placeholder="e.g., Q3 Analysis" 
                autoFocus
            />
          </div>

          {/* Instruction */}
          <div className="grid gap-2">
            <div className="flex items-center gap-2 text-sm font-medium">
                <TextCursorInput className="w-4 h-4 text-purple-500" /> Goal / Instruction
            </div>
            <Textarea 
                value={instruction} 
                onChange={(e) => setInstruction(e.target.value)} 
                placeholder="Describe the task..." 
                className="min-h-[100px]"
            />
          </div>

          {/* File Upload */}
          <div className="grid gap-2">
             <div className="flex items-center gap-2 text-sm font-medium">
                <FileUp className="w-4 h-4 text-amber-500" /> Context Files
            </div>
            <FileUploader files={files} onFilesChange={setFiles} />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={createMutation.isPending}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={createMutation.isPending || !name.trim()}>
            {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Create & Auto-Run
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
