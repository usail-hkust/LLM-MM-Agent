"use client";

import { useEffect, useState, Suspense, useRef } from "react";
import { useConfigStore, useStageStore } from "@/lib/stores";
import { Sidebar } from "@/app/components/layout/Sidebar";
import { Stage } from "@/app/components/layout/Stage";
import { CopilotLayout } from "@/app/components/layout/CopilotLayout";
import { CopilotPanel } from "@/app/components/copilot/CopilotPanel";
import { ProjectManager } from "@/app/components/shared/ProjectManager";
import LandingPage from "@/app/components/home/LandingPage";
import { useSignal } from "@/app/context/SignalContext";
import { useAuth } from "@/app/context/AuthContext";
import { SettingsModal } from "@/app/components/shared/SettingsModal";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useTimelineQuery } from "@/app/lib/queries";
import { TopErrorBoundary } from "@/app/components/shared/TopErrorBoundary";
import { Loader2 } from "lucide-react";

export default function Page() {
  return (
    <Suspense fallback={<div className="h-screen flex items-center justify-center text-slate-400">Loading workspace...</div>}>
      <TopErrorBoundary>
        <Dashboard />
      </TopErrorBoundary>
      <SettingsModal />
    </Suspense>
  );
}

function Dashboard() {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const { setIsOpen } = useConfigStore();
  const { projectId, setProjectId } = useSignal();
  const { selectNode, selectedNodeId, resetStage } = useStageStore();
  const [isSidebarOpen, setSidebarOpen] = useState(true);

  // [FIX Issue 4] Initialization Guard
  // 标记 URL 是否已经解析并同步到了 Store。
  // 在此之前，禁止 Store 的变更反向写回 URL。
  const [isUrlSynced, setIsUrlSynced] = useState(false);

  // 使用 Ref 追踪当前 Store 状态，打破依赖循环
  const stateRef = useRef({ projectId, selectedNodeId });
  useEffect(() => {
    stateRef.current = { projectId, selectedNodeId };
  }, [projectId, selectedNodeId]);

  // 1. URL -> State (Hydration Phase)
  useEffect(() => {
    // 仅执行一次初始化同步
    if (isUrlSynced) return;

    const urlProject = searchParams.get("project");
    const urlNode = searchParams.get("node");

    // [OPTIMIZATION] 批量更新，减少渲染次数
    if (urlProject) {
      setProjectId(urlProject);
      if (urlNode) {
        selectNode(urlNode);
      } else {
        // 显式清空，防止 Store 残留脏数据
        selectNode(null);
      }
    } else {
      // [FIX] 不再自动恢复项目，必须用户手动选择
      // 保持 projectId = null，显示项目选择页面
      setProjectId(null);
      resetStage();
    }

    setIsUrlSynced(true);
  }, [searchParams, isUrlSynced, setProjectId, selectNode, resetStage]);

  // 2. State -> URL (Reflection Phase)
  useEffect(() => {
    if (isLoading || !isUrlSynced) return;

    // [OPTIMIZATION] 使用 URLSearchParams 构造器处理参数，更清洁
    const params = new URLSearchParams(searchParams.toString());
    let hasChanges = false;

    // Project ID Sync
    if (!projectId) {
      if (params.has("project")) {
        params.delete("project");
        params.delete("node");
        hasChanges = true;
      }
    } else {
      if (params.get("project") !== projectId) {
        params.set("project", projectId);
        hasChanges = true;
      }

      // Node ID Sync
      if (selectedNodeId) {
        if (params.get("node") !== selectedNodeId) {
          params.set("node", selectedNodeId);
          hasChanges = true;
        }
      } else {
        if (params.has("node")) {
          params.delete("node");
          hasChanges = true;
        }
      }
    }

    if (hasChanges) {
      // 使用 replace 而非 push，避免污染浏览器历史堆栈
      router.replace(`${pathname}?${params.toString()}`);
    }
  }, [projectId, selectedNodeId, isUrlSynced, isLoading, pathname, router, searchParams]);

  // [REMOVED] Auth Guard - Now LandingPage handles the redirect on user action
  // Old logic: Auto-redirect to login on every page load
  // New logic: Always show LandingPage first, user clicks "Get Started" to redirect
  // useEffect(() => {
  //   if (!isLoading && !user) router.push("/login");
  // }, [user, isLoading, router]);

  // Fetch Timeline for Sidebar
  const { data: timeline, isLoading: isTimelineLoading } = useTimelineQuery(projectId || "");

  // Auto-Redirect Logic
  // [修复] 增加 Ref 防止组件重渲染导致重复重定向
  const hasAutoRedirected = useRef(false);

  // 当项目 ID 变化时，重置重定向标记，允许在新项目中再次自动选择
  useEffect(() => {
    hasAutoRedirected.current = false;
  }, [projectId]);

  useEffect(() => {
    // 只有在项目已加载、时间轴已就绪、当前没有选中节点、且 URL 中也没有节点参数、且 URL 已同步完成时，才执行自动跳转
    if (projectId && !selectedNodeId && timeline && !hasAutoRedirected.current && isUrlSynced) {
      const urlNode = searchParams.get("node");
      if (!urlNode) {
        const targetId = timeline.suggested_next_node || timeline.nodes?.[0]?.id;
        if (targetId) {
          console.log("[AutoRedirect] Selecting suggestion:", targetId);
          hasAutoRedirected.current = true;
          selectNode(targetId);
        }
      }
    }
  }, [projectId, selectedNodeId, timeline, searchParams, selectNode, isUrlSynced]);

  if (isLoading) {
    return (
      <div className="h-screen w-full flex flex-col items-center justify-center gap-3 bg-white text-slate-500">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        <p className="text-sm font-medium">Initializing Workspace...</p>
      </div>
    );
  }

  // View: 未登录用户 - 显示首页介绍
  if (!user) {
    return <LandingPage />;
  }

  // View: 已登录但无项目 - 显示项目选择
  if (!projectId) {
    return <ProjectManager onProjectSelect={(id) => setProjectId(id)} />;
  }

  // View: 已登录且有项目 - 显示工作台
  return (
    <CopilotLayout
      isSidebarOpen={isSidebarOpen}
      onSidebarClose={() => setSidebarOpen(false)}
      sidebar={<Sidebar nodes={timeline?.nodes || []} isLoading={isTimelineLoading} />}
      stage={
        <Stage
          projectId={projectId}
          onBack={() => setProjectId(null)}
          onSettings={() => setIsOpen(true)}
          onToggleSidebar={() => setSidebarOpen(!isSidebarOpen)}
        />
      }
      copilot={<CopilotPanel />}
    />
  );
}
