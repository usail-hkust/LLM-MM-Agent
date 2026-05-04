import { useMemo } from "react";
import { FileJson, Flag, GitFork, Play, RotateCcw } from "lucide-react";
import { HistoryVersion, HistoryArtifact } from "@/app/types";

export interface TimelineNode {
  type: "ROUND" | "FINAL";
  roundIndex: number;
  primaryArtifact: HistoryArtifact;
  subArtifacts: HistoryArtifact[];
  label: string;
  subCountLabel?: string;
  icon: React.ElementType;
}

export function useArtifactGrouping(version: HistoryVersion | null): TimelineNode[] {
  return useMemo(() => {
    if (!version) return [];

    const nodes: TimelineNode[] = [];
    const trigger = (version.trigger || "").toUpperCase();
    const artifacts = version.artifacts || [];

    if (artifacts.length === 0) {
         return [{
            type: "ROUND",
            roundIndex: version.version_index,
            primaryArtifact: { id: "empty", type: "empty", summary: "Processing...", status: "pending", timestamp: 0 },
            subArtifacts: [],
            label: trigger === "INITIAL_RUN" ? "Draft" : "Version",
            icon: Play
         } as any];
    }

    let primary = artifacts[0];
    const subs = artifacts.slice(1);

    let label = "Output";
    let icon = FileJson;

    if (trigger === "INITIAL_RUN") {
        label = "Draft";
        icon = Play;
    } else if (trigger === "REFINE") {
        label = "Refinement";
        icon = RotateCcw;
    } else if (trigger === "SELECT") {
        label = "Selection";
        icon = GitFork;
    }

    if (artifacts.length > 1) {
        const isSCA = artifacts.some(a => a.type.includes("SCA"));
        if (isSCA) {
            label = "Options";
            icon = GitFork;
        }
    }

    nodes.push({
        type: "ROUND",
        roundIndex: version.version_index,
        primaryArtifact: primary,
        subArtifacts: subs,
        label: label,
        subCountLabel: subs.length > 0 ? `+${subs.length}` : undefined,
        icon: icon
    });
    
    return nodes;
  }, [version]);
}
