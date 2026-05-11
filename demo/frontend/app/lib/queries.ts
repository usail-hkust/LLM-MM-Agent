"use client";
import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { apiClient } from "@/app/lib/api-client";
import { useAuth } from "@/app/context/AuthContext";
import * as Schemas from "@/app/api/schemas";
import { UnifiedHistoryEntry } from "@/app/types";
import { WorkflowStatus } from "@/app/api/enums";

// Query Keys Factory
const keys = {
  projects: ["projects"],
  projectDetail: (id: string) => ["projects", id],
  timeline: (id: string) => ["projects", id, "timeline"],
  workspace: (pid: string, nid: string) => ["projects", pid, "nodes", nid, "workspace"],
  nodeHistory: (pid: string, nid: string) => ["projects", pid, "nodes", nid, "history"],
  versions: (pid: string, nid: string) => ["projects", pid, "nodes", nid, "versions"],
  versionDetail: (pid: string, nid: string, vid: string) => ["projects", pid, "nodes", nid, "versions", vid],
};

export function useProjects() {
  const { token } = useAuth();
  return useQuery({
    queryKey: keys.projects,
    queryFn: () => apiClient<Schemas.ProjectSummary[]>("/projects", token),
    enabled: !!token,
  });
}

// [FIX] Added missing hook: useProjectDetail
export function useProjectDetail(projectId: string) {
  const { token } = useAuth();
  return useQuery({
    queryKey: keys.projectDetail(projectId),
    queryFn: () => apiClient<{
      execution_topology: Record<string, Array<{ effective_id: string;[key: string]: any }>>;
      pending_interaction?: Schemas.InteractionRequest | null;
      status?: string;
    }>(`/projects/${projectId}`, token),
    enabled: !!token && !!projectId,
    refetchOnWindowFocus: false,
  });
}

export function useTimelineQuery(projectId: string) {
  const { token } = useAuth();
  return useQuery({
    queryKey: keys.timeline(projectId),
    queryFn: () => apiClient<Schemas.TimelineResponse>(`/projects/${projectId}/timeline`, token),
    enabled: !!token && !!projectId,
    refetchInterval: 5000,
    // [CRITICAL FIX] 强制每次 invalidate 都穿透网络，确保时间轴状态立即同步
    staleTime: 0,
  });
}

export function useNodeWorkspace(projectId: string, nodeId: string | null, options?: { isAgentWorking?: boolean }) {
  const { token } = useAuth();
  return useQuery({
    queryKey: nodeId ? keys.workspace(projectId, nodeId) : [],
    queryFn: () => apiClient<Schemas.NodeWorkspaceView>(`/projects/${projectId}/nodes/${nodeId}`, token),
    enabled: !!token && !!projectId && !!nodeId,
    // [CRITICAL FIX] 确保工作区草稿和动作状态绝对新鲜
    staleTime: 0,
    refetchOnWindowFocus: false,
    // [NEW] 轮询逻辑：当节点正在生成内容时，每2秒刷新一次，直到进入 REVIEWING/FAILED 状态
    refetchInterval: (query) => {
      const status = query.state.data?.state?.status;
      // [FIX] Force polling if Client says agent is working, even if Server hasn't updated status yet
      if (options?.isAgentWorking || status === WorkflowStatus.DRAFTING) return 1000;
      return false;
    },
  });
}

// [FIX] Added missing hook: useNodeHistory
export function useNodeHistory(projectId: string, nodeId: string | null) {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useQuery({
    queryKey: (projectId && nodeId) ? keys.nodeHistory(projectId, nodeId) : [],
    queryFn: () => {
      return apiClient<{ timeline: UnifiedHistoryEntry[] }>(`/projects/${projectId}/nodes/${nodeId}/history`, token);
    },
    enabled: !!token && !!projectId && !!nodeId,
    refetchOnWindowFocus: false,
    staleTime: 0,
    // [OPTIMIZATION] Keep displaying old timeline while fetching new one to reduce UI flicker
    placeholderData: keepPreviousData,
    refetchInterval: (query) => {
      const workspaceKey = nodeId ? keys.workspace(projectId, nodeId) : null;
      const workspaceData = workspaceKey ? qc.getQueryData<Schemas.NodeWorkspaceView>(workspaceKey) : null;
      const status = workspaceData?.state?.status;

      if (status === WorkflowStatus.DRAFTING) return 2000;
      return 5000;
    },
  });
}

export function useNodeVersionDetail(projectId: string, nodeId: string | null, versionId: string | null) {
  const { token } = useAuth();
  return useQuery({
    queryKey: (nodeId && versionId) ? keys.versionDetail(projectId, nodeId, versionId) : [],
    queryFn: () => apiClient<Schemas.NodeWorkspaceView>(`/projects/${projectId}/nodes/${nodeId}/versions/${versionId}`, token),
    enabled: !!token && !!projectId && !!nodeId && !!versionId,
  });
}

export function useSubmitInteraction(projectId: string, nodeId: string | null) {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    // [FIX] 显式注入 node_id 到请求体中
    mutationFn: (req: { action: string; payload: any }) =>
      apiClient(
        `/projects/${projectId}/nodes/${nodeId}/interaction`,
        token,
        {
          method: "POST",
          // 修复点：将 nodeId 合并入 JSON Body，确保满足严格的 Schema 定义
          body: JSON.stringify({ ...req, node_id: nodeId })
        }
      ),
    onSuccess: () => {
      if (nodeId) {
        // 激进失效策略
        qc.invalidateQueries({ queryKey: keys.workspace(projectId, nodeId) });
        qc.invalidateQueries({ queryKey: keys.nodeHistory(projectId, nodeId) });
      }
      qc.invalidateQueries({ queryKey: keys.timeline(projectId) });
      qc.invalidateQueries({ queryKey: keys.projectDetail(projectId) });
    },
  });
}

// [FIX] Added missing Mutations referenced in ControlDeck
export function useRestoreNodeVersion(projectId: string) {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ effectiveNodeId, versionIndex }: { effectiveNodeId: string, versionIndex: number }) =>
      apiClient(`/projects/${projectId}/nodes/${effectiveNodeId}/restore`, token, {
        method: "POST",
        body: JSON.stringify({ version_index: versionIndex })
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: keys.workspace(projectId, vars.effectiveNodeId) });
      qc.invalidateQueries({ queryKey: keys.nodeHistory(projectId, vars.effectiveNodeId) });
      qc.invalidateQueries({ queryKey: keys.timeline(projectId) });
      qc.invalidateQueries({ queryKey: keys.projectDetail(projectId) });
    }
  });
}

export function useForkNode(projectId: string) {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ effectiveNodeId, baseVersionIndex, targetArtifactId }: any) =>
      apiClient(`/projects/${projectId}/nodes/${effectiveNodeId}/fork`, token, {
        method: "POST",
        body: JSON.stringify({ base_version_index: baseVersionIndex, artifact_id: targetArtifactId })
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: keys.workspace(projectId, vars.effectiveNodeId) });
      qc.invalidateQueries({ queryKey: keys.nodeHistory(projectId, vars.effectiveNodeId) });
      qc.invalidateQueries({ queryKey: keys.timeline(projectId) });
      qc.invalidateQueries({ queryKey: keys.projectDetail(projectId) });
    }
  });
}

// [FIX] New Hook for Hard Reset (Interaction reset)
export function useResetNode(projectId: string) {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ effectiveNodeId }: { effectiveNodeId: string }) =>
      apiClient(`/projects/${projectId}/nodes/${effectiveNodeId}/interaction`, token, {
        method: "POST",
        body: JSON.stringify({ action: "reset", node_id: effectiveNodeId })
      }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: keys.workspace(projectId, vars.effectiveNodeId) });
      qc.invalidateQueries({ queryKey: keys.nodeHistory(projectId, vars.effectiveNodeId) });
      qc.invalidateQueries({ queryKey: keys.timeline(projectId) });
      qc.invalidateQueries({ queryKey: keys.projectDetail(projectId) });
    }
  });
}

export function useReexecuteNode(projectId: string) {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ effectiveNodeId }: { effectiveNodeId: string }) =>
      apiClient(`/projects/${projectId}/nodes/${effectiveNodeId}/reexecute`, token, { method: "POST" }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: keys.workspace(projectId, vars.effectiveNodeId) });
      qc.invalidateQueries({ queryKey: keys.projectDetail(projectId) });
      qc.invalidateQueries({ queryKey: keys.timeline(projectId) });
    }
  });
}

export function useUploadAssets() {
  const { token } = useAuth();
  return useMutation({
    mutationFn: (files: File[]) => {
      const fd = new FormData();
      files.forEach(f => fd.append("files", f));
      return apiClient<Schemas.AssetUploadResponse>("/assets/upload", token, { method: "POST", body: fd });
    },
  });
}

export function useCreateProject() {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string } | FormData) => {
      if (data instanceof FormData) {
        return apiClient<{ id: string }>("/projects", token, { method: "POST", body: data });
      }
      return apiClient<{ id: string }>("/projects", token, { method: "POST", body: JSON.stringify(data) });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.projects }),
  });
}

export function useUpdateProject() {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string, data: any }) => apiClient(`/projects/${id}`, token, { method: "PATCH", body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.projects })
  });
}

export function useDeleteProject() {
  const { token } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient(`/projects/${id}`, token, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.projects })
  });
}
