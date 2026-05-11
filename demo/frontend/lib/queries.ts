import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient, apiClientVoid } from "./api";
import { projectKeys } from "./query-keys";
import { ProjectStatusResponse, NodeHistoryResponse } from "@/app/types";
import { toast } from "sonner";

// --- Projects ---

export function useProjects() {
  return useQuery({
    queryKey: projectKeys.lists(),
    queryFn: () => apiClient<ProjectStatusResponse[]>("/projects/"),
  });
}

export function useProjectDetail(id: string | null) {
  return useQuery({
    queryKey: projectKeys.detail(id!),
    queryFn: () => apiClient<ProjectStatusResponse>(`/projects/${id}`),
    enabled: !!id,
    // 智能轮询：如果项目正在运行，每 1s 刷新一次状态
    refetchInterval: (query) => (query.state.data?.status === "RUNNING" ? 1000 : false),
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: FormData) => 
      apiClient<ProjectStatusResponse>("/projects/", { 
        method: "POST", 
        body: data 
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
      toast.success("Project created successfully");
    },
    onError: (err: Error) => toast.error(`Creation failed: ${err.message}`),
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => 
      apiClient(`/projects/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
      toast.success("Project deleted");
    },
    onError: (err: Error) => toast.error(`Deletion failed: ${err.message}`),
  });
}

export function useUpdateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => 
      apiClient<ProjectStatusResponse>(`/projects/${id}`, { 
        method: "PATCH", 
        body: JSON.stringify({ name }) 
      }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
      queryClient.invalidateQueries({ queryKey: projectKeys.detail(variables.id) });
      toast.success("Project renamed");
    },
    onError: (err: Error) => toast.error(`Update failed: ${err.message}`),
  });
}

// --- Node History (Timeline) ---

export function useNodeHistory(projectId: string, nodeId: string | null) {
  return useQuery({
    queryKey: projectKeys.nodeHistory(projectId, nodeId!),
    queryFn: () => {
      let url = `/projects/${projectId}/nodes/${nodeId}/history`;
      // 处理迭代上下文 (Iterative Nodes)
      if (nodeId?.includes("-")) {
        const [base, ...rest] = nodeId.split("-");
        url = `/projects/${projectId}/nodes/${base}/history?iteration_context=${rest.join("-")}`;
      }
      return apiClient<NodeHistoryResponse>(url);
    },
    enabled: !!projectId && !!nodeId,
    // 智能轮询：如果节点正在运行，激进轮询
    refetchInterval: (query) => {
        const data = query.state.data;
        // 1. 安全检查：确保 timeline 是数组且不为空
        if (!data?.timeline || !Array.isArray(data.timeline) || data.timeline.length === 0) {
            return false;
        }
        
        // 2. 安全访问
        const latest = data.timeline[data.timeline.length - 1];
        
        // 3. 状态判断
        const isRunning = latest?.status === "RUNNING" || (data as any)?.active_version === undefined; // active_version undefined usually means initializing
        
        return isRunning ? 1000 : false;
    }
  });
}

const splitNodeId = (effectiveId: string) => {
  const [baseId, ...rest] = effectiveId.split("-");
  return { baseId, iterationContext: rest.length ? rest.join("-") : null };
};

// --- Node Actions ---

export function useRestoreNodeVersion(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ effectiveNodeId, versionIndex }: { effectiveNodeId: string; versionIndex: number }) => {
      const { baseId, iterationContext } = splitNodeId(effectiveNodeId);
      const query = iterationContext ? `?iteration_context=${iterationContext}` : "";
      return apiClientVoid(`/projects/${projectId}/nodes/${baseId}/version${query}`, {
        method: "POST",
        body: JSON.stringify({ version_index: versionIndex }),
      });
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: projectKeys.detail(projectId) });
      queryClient.invalidateQueries({ queryKey: projectKeys.nodeHistory(projectId, variables.effectiveNodeId) });
    },
  });
}

export function useForkNode(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      effectiveNodeId,
      baseVersionIndex,
      targetArtifactId,
    }: {
      effectiveNodeId: string;
      baseVersionIndex: number;
      targetArtifactId: string | null;
    }) => {
      const { baseId, iterationContext } = splitNodeId(effectiveNodeId);
      return apiClientVoid(`/projects/${projectId}/nodes/${baseId}/fork`, {
        method: "POST",
        body: JSON.stringify({
          base_version_index: baseVersionIndex,
          iteration_context: iterationContext,
          target_artifact_id: targetArtifactId,
        }),
      });
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: projectKeys.detail(projectId) });
      queryClient.invalidateQueries({ queryKey: projectKeys.nodeHistory(projectId, variables.effectiveNodeId) });
    },
  });
}

export function useReexecuteNode(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ effectiveNodeId }: { effectiveNodeId: string }) => {
      const { baseId, iterationContext } = splitNodeId(effectiveNodeId);
      return apiClientVoid(`/projects/${projectId}/nodes/${baseId}/re-execute`, {
        method: "POST",
        body: JSON.stringify({ iteration_context: iterationContext }),
      });
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: projectKeys.detail(projectId) });
      queryClient.invalidateQueries({ queryKey: projectKeys.nodeHistory(projectId, variables.effectiveNodeId) });
    },
  });
}

export function useResumeProject(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClientVoid(`/projects/${projectId}/resume`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.detail(projectId) });
      queryClient.invalidateQueries({ queryKey: projectKeys.lists() });
    },
  });
}

export function useSubmitInteraction(projectId: string) {
  return useMutation({
    mutationFn: ({ interactionId, payload }: { interactionId: string; payload: Record<string, any> }) =>
      apiClientVoid(`/projects/${projectId}/interactions/${interactionId}/submit`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}
