"use client";
import { UnifiedHeader } from "@/app/components/stage/layout/UnifiedHeader";
import { Viewport } from "@/app/components/stage/Viewport";
import { useNodeWorkspace, useProjects, useProjectDetail } from "@/app/lib/queries"; 
import { useStageStore } from "@/lib/stores";
import { useLiveWorkflowSync } from "@/app/hooks/useLiveWorkflowSync";
// [FIX ISSUE 4] Import
import { GlobalBeacon } from "@/app/components/stage/GlobalBeacon";

export function Stage({ projectId, onBack, onSettings, onToggleSidebar }: any) {
  const { selectedNodeId } = useStageStore();
  const { data: projects } = useProjects();
  
  // [FIX] 激活实时同步
  useLiveWorkflowSync(projectId);
  
  // [FIX] 获取 Project 详情以获取 execution_topology 和 pending_interaction
  const { data: projectDetail } = useProjectDetail(projectId);
  const { data: workspace } = useNodeWorkspace(projectId, selectedNodeId);
  
  return (
    <div className="flex flex-col h-full w-full bg-white relative min-w-0">
      <UnifiedHeader 
          projectId={projectId} 
          projectName={projects?.find((p:any) => p.id===projectId)?.name} 
          workspace={workspace} 
          projectStatus={projectDetail?.status}
          pendingInteraction={projectDetail?.pending_interaction}
          isSidebarOpen={true} 
          onToggleSidebar={onToggleSidebar} 
          onBack={onBack} 
          onSettings={onSettings} 
      />
      
      {/* [FIX ISSUE 4] Mount Beacon */}
      <GlobalBeacon pendingNodeId={projectDetail?.pending_interaction?.node_id} />

      <div className="flex-1 min-h-0 relative z-0">
          <Viewport 
              projectId={projectId} 
              nodeId={selectedNodeId} 
              // [CRITICAL] 透传 pendingInteraction 到 Viewport
              pendingInteraction={projectDetail?.pending_interaction}
          />
      </div>
    </div>
  );
}
