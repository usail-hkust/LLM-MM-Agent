"use client";

import React, { useState, useEffect } from "react";
import { RenderAtomProps } from "@/app/domain/abp";
import { useAtomBinding } from "@/app/hooks/useAtomBinding";
import { MarkdownDisplay } from "@/app/components/shared/MarkdownDisplay";
import { Check, X, Edit3, Save } from "lucide-react";
import { AtomShell } from "../atoms/AtomShell";

export const EntityVarlCard: React.FC<RenderAtomProps> = (props) => {
    const { block, actions, onAction } = props;
    const { value, onChange, isReadOnly } = useAtomBinding(props);
    const [isEditing, setIsEditing] = useState(false);
    
    // Defensive initialization
    const rawContent = typeof value !== 'undefined' ? value : block.content;
    const contentString = typeof rawContent === "string"
        ? rawContent
        : (rawContent ? JSON.stringify(rawContent, null, 2) : "");

    const [editValue, setEditValue] = useState(contentString);

    // Sync local state if external binding updates
    useEffect(() => { setEditValue(contentString); }, [contentString]);

    const handleEdit = () => {
        setEditValue(contentString);
        setIsEditing(true);
    };

    // [FIX] Added persistence logic
    const handleSave = () => {
        if (!isReadOnly) {
            onChange(editValue); // Commit to form state
        }
        setIsEditing(false);

        // Optional: Trigger explicit save action immediately if required
        const saveAction = actions.find(a => a.id === "save" || a.id === "save_draft");
        if (saveAction) {
             onAction({ ...saveAction, payload: { ...saveAction.payload, content: editValue } });
        }
    };

    const handleApprove = () => {
        const approveAction = actions.find((a) => a.id === "finalize" || a.label?.toLowerCase() === "finalize");
        if (approveAction) onAction(approveAction);
    };

    const handleReject = () => {
        const rejectAction = actions.find((a) => a.id === "reject");
        if (rejectAction) onAction(rejectAction);
    };

    return (
        <AtomShell {...props} hideHeader variant="default">
            {() => (
                <div className="flex flex-col gap-4">
                    <div className="flex items-center justify-between pb-4 border-b border-slate-100">
                        <h3 className="text-lg font-bold text-slate-800">{block.label || "Problem Analysis"}</h3>
                        {!isReadOnly && (
                            <div className="flex items-center gap-2">
                                {isEditing ? (
                                    <button onClick={handleSave} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors">
                                        <Save className="w-3.5 h-3.5" /> Save
                                    </button>
                                ) : (
                                    <button onClick={handleEdit} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-slate-600 bg-white border border-slate-200 rounded-md hover:bg-slate-50 transition-colors">
                                        <Edit3 className="w-3.5 h-3.5" /> Edit
                                    </button>
                                )}
                            </div>
                        )}
                    </div>

                    <div className="min-h-[200px]">
                        {isEditing ? (
                            <textarea
                                className="w-full h-96 p-4 text-sm font-mono border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-slate-50 resize-none"
                                value={editValue}
                                onChange={(e) => setEditValue(e.target.value)}
                            />
                        ) : (
                            <div className="prose prose-sm max-w-none text-slate-600">
                                <MarkdownDisplay content={contentString} />
                            </div>
                        )}
                    </div>

                    {!isReadOnly && !isEditing && (
                        <div className="flex items-center gap-3 pt-4 border-t border-slate-100 mt-4">
                            <button onClick={handleReject} className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl border border-red-200 bg-red-50 text-red-700 font-bold text-sm hover:bg-red-100 transition-all">
                                <X className="w-4 h-4" /> Reject
                            </button>
                            <button onClick={handleApprove} className="flex-[2] flex items-center justify-center gap-2 py-2.5 rounded-xl bg-black text-white font-bold text-sm hover:bg-slate-800 transition-all shadow-sm">
                                <Check className="w-4 h-4" /> Approve
                            </button>
                        </div>
                    )}
                </div>
            )}
        </AtomShell>
    );
};
