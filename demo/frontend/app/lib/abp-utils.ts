// Polyfill for crypto.randomUUID compatibility with older browsers
if (typeof crypto !== 'undefined' && !crypto.randomUUID) {
  (crypto.randomUUID as any) = () => {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  };
}

import { ContentBlock, NodeOutput, BlockType, isNodeOutput, resolveBindingKey } from "@/app/domain/abp";
import { ExecutionArtifact } from "@/app/lib/api-types";

/**
 * [Zero-Guessing Normalization]
 * Converts any API response into a valid NodeOutput structure.
 *
 * Logic:
 * 1. If it walks like a NodeOutput, it is a NodeOutput.
 * 2. If not, wrap it based on primitive type (String -> MARKDOWN, Object -> DATA).
 * 3. No deep inspection or string parsing.
 */
export function normalizeToABP(data: any): NodeOutput {
  // 1. Trust the Protocol
  if (isNodeOutput(data)) {
    // Ensure all blocks have IDs
    const ensure = (b: any) => {
      if (!b.id) b.id = crypto.randomUUID();
      if (b.children) b.children.forEach(ensure);
    };
    data.blocks.forEach(ensure);
    return data;
  }

  // 1.5 Loose compliance (legacy structure that mimics ABP)
  if (data && typeof data === "object" && Array.isArray(data.blocks)) {
    const ensure = (b: any) => {
      if (!b.id) b.id = crypto.randomUUID();
      if (b.children) b.children.forEach(ensure);
    };
    data.blocks.forEach(ensure);
    return {
      thought: typeof data.thought === "string" ? data.thought : "",
      blocks: data.blocks,
      metadata: (data as any).metadata || {},
    };
  }

  // 2. Handle Primitives (Fallback)
  if (data === null || data === undefined) {
    return { thought: "", blocks: [] };
  }

  // String -> Markdown
  if (typeof data === "string") {
    return {
      thought: "",
      blocks: [
        {
          id: `fallback-${Date.now()}`,
          type: BlockType.MARKDOWN,
          label: "Output",
          content: data,
          tags: [],
          meta: {},
        },
      ],
    };
  }

  // Object/Array -> Data
  if (typeof data === "object") {
    const isArray = Array.isArray(data);
    return {
      thought: "",
      blocks: [
        {
          id: `fallback-data-${Date.now()}`,
          type: BlockType.DATA,
          label: isArray ? "List Data" : "Data Object",
          content: data,
          tags: [],
          meta: {},
        },
      ],
    };
  }

  return { thought: "", blocks: [] };
}

/**
 * [Defensive Payload Unwrap]
 * Normalizes polymorphic payloads into a direct data object.
 * Handles NodeOutput blocks, legacy { data: ... } wrappers, and raw objects.
 */
export function normalizeDataPayload(payload: any): Record<string, any> {
  let current = payload || {};

  // Strategy 1: NodeOutput Protocol (blocks array)
  if (current.blocks && Array.isArray(current.blocks)) {
    const dataBlock = current.blocks.find(
      (b: any) =>
        b.type === "DATA" ||
        b.type === "json" ||
        (b.tags && Array.isArray(b.tags) && (b.tags.includes("json") || b.tags.includes("data")))
    );

    if (dataBlock && dataBlock.content && typeof dataBlock.content === "object") {
      current = dataBlock.content;
    }
  }

  // Strategy 2: Legacy "data" wrapper
  // [FIX] 防止误判：如果对象包含 'outline'，则它不是 legacy wrapper，而是有效载荷本身
  const isLegacyWrapper =
    current.data &&
    typeof current.data === "object" &&
    !Array.isArray(current.data) &&
    !current.sub_problem_list &&
    !current.outline &&
    !current.structure &&
    !current.items;

  if (isLegacyWrapper) {
    current = current.data;
  }

  return current;
}

/**
 * [CRITICAL FIX] 深度 Hydration
 * 使用与 useAtomBinding 相同的 resolveBindingKey 策略，将 Block 内容扁平化写入 new_content
 */
export function hydrateFormFromABP(data: any): Record<string, any> {
  const nodeOutput = normalizeToABP(data);
  const formData: Record<string, any> = { new_content: {} };

  const traverse = (blocks: ContentBlock[]) => {
    for (const block of blocks) {
      const key = resolveBindingKey(block);
      if (key && block.content !== undefined && block.content !== null) {
        formData.new_content[key] = block.content;
      }
      if (block.children?.length) traverse(block.children);
    }
  };
  traverse(nodeOutput.blocks || []);
  return formData;
}

/**
 * [FIX] 增强版 Artifact 提取器
 * 递归扫描 DATA 和 CONTAINER 块，提取嵌入的或标记为 artifact 的数据。
 * [OPTIMIZED] Ensure blob_hash is extracted to enable CAS fallback loading.
 */
export function extractArtifactsFromABP(data: any): ExecutionArtifact[] {
  const artifacts: ExecutionArtifact[] = [];
  const nodeOutput = normalizeToABP(data);

  const traverse = (blocks: ContentBlock[]) => {
    for (const block of blocks) {
      // 1. 显式 FILE 块
      if (block.type === BlockType.FILE) {
        artifacts.push({
          id: block.meta?.id || block.meta?.artifact_id || block.id,
          name: block.label || block.meta?.filename || `Artifact ${artifacts.length + 1}`,
          type: block.meta?.mime_type || "application/octet-stream",
          data: block.content,
          url: block.meta?.url,
          blobHash: block.meta?.blob_hash, // [CRITICAL FIX] Map blob_hash
        });
      } 
      
      // 2. 隐式 Data Artifact (通过标签识别)
      else if (
          block.type === BlockType.DATA &&
          (block.tags?.includes("artifact") || block.tags?.includes("visual"))
      ) {
          artifacts.push({
            id: block.meta?.id || block.id,
            name: block.meta?.filename || block.label || "Data Artifact",
            type: block.meta?.mime_type || "application/json",
            data: block.content,
            url: block.meta?.url,
            blobHash: block.meta?.blob_hash, // [CRITICAL FIX] Map blob_hash
          });
      }

      // 3. [Critical] 扫描执行结果中的 Artifacts
      if (block.meta?.execution_result && typeof block.meta.execution_result === "object") {
         const execRes = block.meta.execution_result as any;
         if (Array.isArray(execRes.artifacts)) {
             execRes.artifacts.forEach((art: any) => {
                 artifacts.push({
                     id: art.id || `emb-${artifacts.length}`,
                     name: art.name || "Generated Artifact",
                     type: art.type || "application/octet-stream",
                     data: art.data,
                     url: art.url,
                     blobHash: art.blob_hash || art.blobHash // [CRITICAL FIX] Map blob_hash
                 });
             });
         }
      }

      if (block.type === BlockType.CONTAINER && block.children?.length) {
        traverse(block.children);
      }
    }
  };

  traverse(nodeOutput.blocks);
  
  // 去重
  const seen = new Set();
  return artifacts.filter(a => {
      const key = a.id || a.name;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
  });
}

/**
 * Helper: merges multiple NodeOutput objects.
 */
export function mergeNodeOutputs(outputs: NodeOutput[]): NodeOutput {
  return {
    thought: outputs.map((o) => o.thought).filter(Boolean).join("\n\n---\n\n"),
    blocks: outputs.flatMap((o) => o.blocks),
  };
}

// --- Simplified Accessors (Zero-Guessing) ---

export function findBlockByTag(blocks: ContentBlock[], tag: string): ContentBlock | undefined {
  for (const block of blocks) {
    if (block.tags?.includes(tag)) return block;
    if (block.type === BlockType.CONTAINER && block.children?.length) {
      const nested = findBlockByTag(block.children, tag);
      if (nested) return nested;
    }
  }
  return undefined;
}

export function findBlocksByType(blocks: ContentBlock[], type: BlockType): ContentBlock[] {
  const results: ContentBlock[] = [];
  for (const block of blocks) {
    if (block.type === type) results.push(block);
    if (block.type === BlockType.CONTAINER && block.children?.length) {
      results.push(...findBlocksByType(block.children, type));
    }
  }
  return results;
}

/**
 * Extracts Source Code strictly by Tag or Type.
 */
export function getCodeBlock(data: any): ContentBlock | null {
  const { blocks } = normalizeToABP(data);

  return (
    findBlockByTag(blocks, "source_code") ||
    findBlocksByType(blocks, BlockType.CODE)[0] ||
    null
  );
}

/**
 * Extracts Logs strictly by Tag.
 * Note: Backend now returns logs as MARKDOWN with "execution_logs" tag.
 */
export function getLogBlocks(data: any): ContentBlock[] {
  const { blocks } = normalizeToABP(data);

  const allBlocks = findBlocksByType(blocks, BlockType.MARKDOWN).concat(
    findBlocksByType(blocks, BlockType.DATA),
    findBlocksByType(blocks, BlockType.CODE)
  );

  return allBlocks.filter(
    (b) =>
      b.tags?.includes("execution_logs") ||
      b.tags?.includes("logs") ||
      b.tags?.includes("compilation_log")
  );
}
