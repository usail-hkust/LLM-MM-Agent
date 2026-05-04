"use client";

import React from "react";
import { RenderAtomProps } from "@/app/domain/abp";
import { useAtomBinding } from "@/app/hooks/useAtomBinding";
import { MarkdownDisplay } from "@/app/components/shared/MarkdownDisplay";
import { AtomShell } from "../atoms/AtomShell";
import { Sparkles, Terminal, FileCode } from "lucide-react";

export const EntityResultCard: React.FC<RenderAtomProps> = (props) => {
    const { block } = props;
    const { value } = useAtomBinding(props);

    const rawContent = typeof value === "string" ? value : block.content || "";

    // Clean up content:
    // The backend concatenates context like:
    // ## PROBLEM ANALYSIS
    // ...
    // ## EXECUTION LOGS
    // ...
    // ## RESULT ANALYSIS
    // (actual content)
    // We want to extract just the Result Analysis part if possible, or at least structure the display.

    // Simple heuristic parser
    const contentStr = typeof rawContent === 'string' ? rawContent : JSON.stringify(rawContent);
    const sections = parseSections(contentStr);
    const resultSection = sections.find(s => s.title.toUpperCase().includes("RESULT")) || sections.find(s => s.title === "UNKNOWN") || { title: "Result", content: contentStr };

    return (
        <AtomShell {...props} hideHeader variant="default">
            {() => (
                <div className="flex flex-col gap-6">
                    {/* Header */}
                    <div className="flex items-center gap-2 pb-4 border-b border-slate-100">
                        <div className="p-2 bg-gradient-to-br from-purple-500 to-blue-500 rounded-lg shadow-sm">
                            <Sparkles className="w-5 h-5 text-white" />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-slate-800 leading-tight">
                                {block.label || "Result Analysis"}
                            </h3>
                            <p className="text-xs text-slate-500 mt-0.5">Automated synthesis of execution results</p>
                        </div>
                    </div>

                    {/* Main Content */}
                    <div className="prose prose-sm max-w-none prose-headings:font-bold prose-headings:text-slate-800 text-slate-600">
                        <MarkdownDisplay content={resultSection.content} />
                    </div>

                    {/* Collapsed Context Sections (Optional, or just hide them) */}
                    {/* We could add toggles here to show the logs/source if needed, but the user complained about "extra content", so we hide them by default */}
                </div>
            )}
        </AtomShell>
    );
};

interface Section {
    title: string;
    content: string;
}

function parseSections(text: string): Section[] {
    const lines = text.split('\n');
    const sections: Section[] = [];
    let currentTitle = "UNKNOWN";
    let currentContent: string[] = [];

    const flush = () => {
        if (currentContent.length > 0) {
            sections.push({ title: currentTitle, content: currentContent.join('\n').trim() });
        }
    };

    for (const line of lines) {
        if (line.startsWith('## ')) {
            flush();
            currentTitle = line.replace('## ', '').trim();
            currentContent = [];
        } else {
            currentContent.push(line);
        }
    }
    flush();

    return sections;
}
