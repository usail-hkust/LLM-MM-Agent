"use client";

import { useState, useMemo, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import {
    Plus,
    Search,
    MoreHorizontal,
    Trash2,
    Edit2,
    FolderOpen,
    Clock,
    FileText,
    Sparkles,
    LayoutGrid,
    List as ListIcon,
    ArrowRight,
    CalendarDays,
    Download,
    Loader2,
    Settings, // [FIX] Import Settings icon
    LogOut // Import LogOut icon
} from "lucide-react";
import { useUI } from "@/app/hooks/useUI";
import { useProjectExport } from "@/app/hooks/useProjectExport";
import { CreateProjectModal } from "@/app/components/shared/CreateProjectModal";
import { ProjectSummary } from "@/app/api/schemas";
import { useProjects, useDeleteProject, useUpdateProject } from "@/app/lib/queries";
import { useAuth } from "@/app/context/AuthContext";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useConfigStore } from "@/lib/stores"; // [FIX] Import config store

// --- Utility: Date Formatter ---
function formatRelativeTime(dateString: string) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    // Within 24 hours
    if (diff < 24 * 60 * 60 * 1000) {
        if (diff < 60 * 60 * 1000) {
            const mins = Math.max(1, Math.floor(diff / 60000));
            return `${mins} min${mins > 1 ? 's' : ''} ago`;
        }
        const hours = Math.floor(diff / 3600000);
        return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    }

    // Older
    return new Intl.DateTimeFormat('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    }).format(date);
}

// --- Component: Project Manager (Main Container) ---

export function ProjectManager({ onProjectSelect }: { onProjectSelect: (id: string) => void }) {
    const { setIsOpen } = useConfigStore(); // [FIX] Access store
    const [searchQuery, setSearchQuery] = useState("");
    const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
    const [isModalOpen, setIsModalOpen] = useState(false);
    const { user, logout } = useAuth(); // Get user and logout function
    const router = useRouter(); // For navigation

    // 1. 数据获取 (自动处理 Loading/Error/Caching)
    const { data: projects, isLoading, isError } = useProjects();
    const deleteMutation = useDeleteProject();
    const updateMutation = useUpdateProject();

    const { dialog } = useUI();

    // Handle logout
    const handleLogout = async () => {
        const confirmed = await dialog.confirm("Are you sure you want to log out?", {
            title: "Log Out",
            confirmText: "Log Out"
        });
        if (confirmed) {
            logout();
            router.push("/");
        }
    };

    // 2. Client-side Filtering
    const filteredProjects = useMemo(() => {
        if (!projects) return [];
        const lowerQ = searchQuery.toLowerCase();
        // Sort by updated_at descending (newest first), fallback to ID logic if updated_at missing
        return projects
            .slice()
            .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
            .filter(p =>
                p.name.toLowerCase().includes(lowerQ) ||
                p.id.toLowerCase().includes(lowerQ)
            );
    }, [projects, searchQuery]);

    const handleDelete = async (id: string) => {
        const confirmed = await dialog.confirm("Delete this project? Project history will be lost forever.", {
            title: "Delete Project",
            danger: true,
            confirmText: "Delete Project"
        });
        if (!confirmed) return;
        deleteMutation.mutate(id);
    };

    const handleRename = async (id: string, currentName: string) => {
        const newName = await dialog.prompt("Rename project:", {
            defaultValue: currentName,
            title: "Rename Project"
        });
        if (!newName || newName === currentName) return;
        updateMutation.mutate({ id, data: { name: newName } });
    };

    // --- Render ---

    return (
        // [FIX Issue 1 & 3] 
        // 1. h-screen: Take full viewport height
        // 2. flex-col: Organize Header and Content vertically
        // 3. bg-slate-50: Consistent background
        <div className="flex flex-col h-screen w-full bg-slate-50 overflow-hidden">

            {/* Header Section (Fixed at top) */}
            <div className="w-full bg-white border-b border-slate-200 z-10 shrink-0">
                <div className="max-w-7xl mx-auto px-6 py-5">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div>
                            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Projects</h1>
                            <p className="text-slate-500 text-sm mt-1">Manage and monitor your AI agent workflows.</p>
                        </div>

                        <div className="flex items-center gap-2">
                            {/* Search Bar */}
                            <div className="relative group">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-blue-500 transition-colors" />
                                <Input
                                    placeholder="Search projects..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    className="pl-9 w-full md:w-64 bg-slate-50 border-slate-200 focus:bg-white transition-all"
                                />
                            </div>

                            {/* View Toggle (Desktop Only) */}
                            <div className="hidden md:flex bg-slate-100 p-1 rounded-lg border border-slate-200">
                                <button
                                    onClick={() => setViewMode("grid")}
                                    className={cn("p-1.5 rounded-md transition-all", viewMode === "grid" ? "bg-white shadow-sm text-slate-800" : "text-slate-400 hover:text-slate-600")}
                                    aria-label="Grid View"
                                >
                                    <LayoutGrid className="w-4 h-4" />
                                    <span className="sr-only">Grid View</span>
                                </button>
                                <button
                                    onClick={() => setViewMode("list")}
                                    className={cn("p-1.5 rounded-md transition-all", viewMode === "list" ? "bg-white shadow-sm text-slate-800" : "text-slate-400 hover:text-slate-600")}
                                    aria-label="List View"
                                >
                                    <ListIcon className="w-4 h-4" />
                                    <span className="sr-only">List View</span>
                                </button>
                            </div>

                            {/* [FIX] Settings Button */}
                            <button
                                onClick={() => setIsOpen(true)}
                                className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors border border-transparent hover:border-slate-200"
                                aria-label="Settings"
                                title="Global Settings"
                            >
                                <Settings className="w-5 h-5" />
                            </button>

                            {/* Logout Button */}
                            <button
                                onClick={handleLogout}
                                className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors border border-transparent hover:border-red-200"
                                aria-label="Log Out"
                                title="Log Out"
                            >
                                <LogOut className="w-5 h-5" />
                            </button>

                            {/* Primary Action Button (Desktop) */}
                            <Button
                                onClick={() => setIsModalOpen(true)}
                                className="hidden md:flex bg-slate-900 hover:bg-black text-white"
                            >
                                <Plus className="w-4 h-4 mr-2" /> New Project
                            </Button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Content Section (Scrollable) */}
            {/* [FIX Issue 3] flex-1 + overflow-y-auto enables internal scrolling */}
            <div className="flex-1 overflow-y-auto custom-scrollbar">
                {/* [FIX Issue 1] Max-width container handles spacing */}
                <div className="max-w-7xl mx-auto px-6 py-8 pb-24">
                    {isLoading ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                            {[1, 2, 3, 4].map(i => <ProjectCardSkeleton key={i} />)}
                        </div>
                    ) : isError ? (
                        <div className="flex flex-col items-center justify-center p-20 text-center border-2 border-dashed border-red-100 rounded-2xl bg-red-50/50">
                            <span className="text-red-500 font-bold mb-2">Failed to load projects</span>
                            <span className="text-xs text-red-400">Please check your network connection.</span>
                        </div>
                    ) : filteredProjects.length === 0 ? (
                        <EmptyState onCreate={() => setIsModalOpen(true)} />
                    ) : (
                        <div className={cn(
                            "grid gap-4",
                            viewMode === "grid"
                                ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
                                : "grid-cols-1"
                        )}>
                            {filteredProjects.map(project => (
                                <ProjectCard
                                    key={project.id}
                                    project={project}
                                    viewMode={viewMode}
                                    onSelect={() => onProjectSelect(project.id)}
                                    onRename={() => handleRename(project.id, project.name)}
                                    onDelete={() => handleDelete(project.id)}
                                />
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Mobile Floating Action Button (FAB) */}
            <button
                onClick={() => setIsModalOpen(true)}
                className="md:hidden fixed bottom-6 right-6 w-14 h-14 bg-blue-600 text-white rounded-full shadow-xl flex items-center justify-center z-50 hover:scale-105 active:scale-95 transition-transform"
                aria-label="Create New Project"
            >
                <Plus className="w-6 h-6" />
                <span className="sr-only">Create New Project</span>
            </button>

            <CreateProjectModal
                isOpen={isModalOpen}
                onOpenChange={setIsModalOpen}
                onSuccess={(id) => {
                    setIsModalOpen(false);
                    onProjectSelect(id);
                }}
            />
        </div>
    );
}

// --- Sub-Component: Project Card ---

function ProjectCard({
    project,
    viewMode,
    onSelect,
    onRename,
    onDelete
}: {
    project: ProjectSummary,
    viewMode: "grid" | "list",
    onSelect: () => void,
    onRename: () => void,
    onDelete: () => void
}) {
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);
    const timeDisplay = formatRelativeTime(project.updated_at);
    
    // Export Hook Integration
    const { triggerExport, isExporting } = useProjectExport();

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setIsMenuOpen(false);
            }
        };
        // Use mousedown to capture clicks before click triggers
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const toggleMenu = (e: React.MouseEvent) => {
        e.stopPropagation(); // Stop card click
        e.preventDefault();
        setIsMenuOpen(!isMenuOpen);
    };

    return (
        <div
            onClick={onSelect}
            className={cn(
                "group relative bg-white border border-slate-200 rounded-xl transition-all duration-200 cursor-pointer overflow-visible",
                // [FIX Issue 4] Flicker Fix:
                // Only apply translate-y hover effect in GRID mode. 
                // In List mode, the translate effect shifts the button under the mouse, causing rapid hover toggling.
                viewMode === "grid"
                    ? "flex flex-col h-[180px] hover:-translate-y-1 hover:shadow-md hover:border-blue-300"
                    : "flex items-center p-4 hover:bg-slate-50 hover:border-blue-200",

                // [FIX Issue 4] Z-Index Fix:
                // When menu is open, boost Z-Index so the dropdown isn't clipped or fighting with lower cards
                isMenuOpen ? "z-20 ring-2 ring-blue-100 border-blue-300" : "z-0"
            )}
        >
            {/* 1. Content Area */}
            <div className={cn(
                "flex justify-between items-start relative",
                viewMode === "grid" ? "p-5 pb-2 w-full" : "flex-1 items-center gap-4"
            )}>
                <div className="flex-1 min-w-0">
                    {/* Status Badge (Visual Only for now) */}
                    <div className="flex items-center gap-2 mb-2">
                        {/* Optional: Add logic to check project.updated_at vs now for 'Active' vs 'Stale' */}
                        <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase border border-transparent bg-emerald-50 text-emerald-600">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                            Active
                        </span>
                    </div>

                    <h3 className="font-bold text-slate-800 text-base truncate group-hover:text-blue-700 transition-colors">
                        {project.name}
                    </h3>

                    {/* Description / ID */}
                    <p className="text-xs text-slate-400 mt-1 line-clamp-1 font-mono opacity-70">
                        {project.id.split('-')[0]}...
                    </p>
                </div>

                {/* [FIX Issue 2] List View Specific Timestamp */}
                {viewMode === "list" && (
                    <div className="hidden sm:flex flex-col items-end mr-4 text-right">
                        <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
                            <Clock className="w-3.5 h-3.5" />
                            {timeDisplay}
                        </div>
                        <span className="text-[10px] text-slate-400 mt-0.5">Last updated</span>
                    </div>
                )}

                {/* 2. Menu Button */}
                <div className={cn("relative flex-shrink-0", viewMode === "list" ? "ml-2" : "")} ref={menuRef}>
                    <button
                        onClick={toggleMenu}
                        className={cn(
                            "p-2 rounded-lg transition-colors",
                            isMenuOpen
                                ? "bg-slate-100 text-slate-900"
                                : "text-slate-400 hover:text-slate-800 hover:bg-slate-100"
                        )}
                        aria-label="Project Actions"
                    >
                        <MoreHorizontal className="w-5 h-5" />
                        <span className="sr-only">Project Actions</span>
                    </button>

                    {/* Dropdown Menu */}
                    {isMenuOpen && (
                        <div className="absolute right-0 top-full mt-1 w-48 bg-white rounded-lg shadow-xl border border-slate-100 py-1 z-50 animate-in fade-in zoom-in-95 duration-100 origin-top-right">
                            <button
                                onClick={(e) => { e.stopPropagation(); onSelect(); }}
                                className="w-full text-left px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                            >
                                <FolderOpen className="w-4 h-4 text-slate-400" /> Open Project
                            </button>
                            <button
                                onClick={(e) => { e.stopPropagation(); setIsMenuOpen(false); onRename(); }}
                                className="w-full text-left px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                            >
                                <Edit2 className="w-4 h-4 text-slate-400" /> Rename
                            </button>
                            
                            {/* Export Button */}
                            <button
                                onClick={(e) => { e.stopPropagation(); setIsMenuOpen(false); triggerExport(project.id); }}
                                disabled={isExporting}
                                className="w-full text-left px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2 disabled:opacity-50"
                            >
                                {isExporting ? <Loader2 className="w-4 h-4 animate-spin text-slate-400" /> : <Download className="w-4 h-4 text-slate-400" />}
                                Export Archive
                            </button>

                            <div className="h-px bg-slate-100 my-1" />
                            <button
                                onClick={(e) => { e.stopPropagation(); setIsMenuOpen(false); onDelete(); }}
                                className="w-full text-left px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
                            >
                                <Trash2 className="w-4 h-4" /> Delete Permanently
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* 3. Footer (Grid Mode Only) */}
            {viewMode === "grid" && (
                <div className="mt-auto p-5 pt-3 border-t border-slate-50 flex items-center justify-between text-[10px] font-medium text-slate-400">
                    <div className="flex items-center gap-1.5" title="Workflow Type">
                        <FileText className="w-3 h-3" />
                        <span>Generic Agent</span>
                    </div>
                    {/* [FIX Issue 2] Grid View Timestamp */}
                    <div className="flex items-center gap-1.5 text-slate-500">
                        <CalendarDays className="w-3 h-3" />
                        <span>{timeDisplay}</span>
                    </div>
                </div>
            )}
        </div>
    );
}

// --- Sub-Component: Empty State ---

function EmptyState({ onCreate }: { onCreate: () => void }) {
    return (
        <div className="flex flex-col items-center justify-center py-20 px-4 text-center animate-in fade-in slide-in-from-bottom-4 duration-700">
            <div className="w-24 h-24 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-full flex items-center justify-center mb-6 shadow-sm ring-8 ring-blue-50/50">
                <Sparkles className="w-10 h-10 text-blue-600" />
            </div>
            <h2 className="text-2xl font-bold text-slate-900 mb-2">Welcome to MM Agent Platform</h2>
            <p className="text-slate-500 max-w-md mb-8 leading-relaxed">
                You haven't created any workflows yet. Start by creating a new project to see the agent in action.
            </p>

            {/* Unified Action Button */}
            <button
                onClick={onCreate}
                className="group flex flex-col items-center justify-center p-8 bg-white border-2 border-slate-200 hover:border-blue-500 hover:shadow-xl rounded-2xl transition-all duration-300 relative overflow-hidden max-w-sm w-full"
            >
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                    <Plus className="w-24 h-24 text-blue-600" />
                </div>
                <div className="w-12 h-12 bg-black text-white rounded-xl flex items-center justify-center mb-4 shadow-md group-hover:scale-110 transition-transform">
                    <Plus className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-bold text-slate-900 group-hover:text-blue-700 transition-colors">Create New Workflow</h3>
                <p className="text-sm text-slate-500 mt-2 text-center leading-relaxed max-w-[280px]">
                    Initialize a new agent session with custom objectives and context files.
                </p>
                <div className="mt-6 flex items-center gap-2 text-xs font-bold text-blue-600 opacity-0 group-hover:opacity-100 transition-all transform translate-y-2 group-hover:translate-y-0">
                    Get Started <ArrowRight className="w-3.5 h-3.5" />
                </div>
            </button>
        </div>
    );
}

function ProjectCardSkeleton() {
    return (
        <div className="bg-white border border-slate-100 rounded-xl p-5 h-[180px] flex flex-col gap-4">
            <div className="flex justify-between items-start">
                <div className="space-y-3 w-full">
                    <Skeleton className="w-16 h-5 rounded-full bg-slate-100" />
                    <Skeleton className="w-3/4 h-6 rounded bg-slate-100" />
                    <Skeleton className="w-1/2 h-4 rounded bg-slate-100" />
                </div>
                <Skeleton className="w-8 h-8 rounded-lg bg-slate-100 shrink-0" />
            </div>
            <div className="mt-auto pt-3 border-t border-slate-50 flex justify-between">
                <Skeleton className="w-16 h-3 rounded bg-slate-100" />
                <Skeleton className="w-20 h-3 rounded bg-slate-100" />
            </div>
        </div>
    );
}
