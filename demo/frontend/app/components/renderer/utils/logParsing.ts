import { ExecutionLog } from "@/app/types";

const TAG_PATTERN = /\[(STDOUT|STDERR|THOUGHT|RESULT|LOGS|SYSTEM)\]/g;
const TAG_STRIP_PATTERN = /\[(STDOUT|STDERR|THOUGHT|RESULT|LOGS|SYSTEM)\]/g;
const TAG_TYPE_MAP: Record<string, ExecutionLog["type"]> = {
  STDOUT: "stdout",
  STDERR: "stderr",
  THOUGHT: "thought",
  RESULT: "system",
  LOGS: "system",
  SYSTEM: "system",
};

function splitLogLines(raw: string): string[] {
  if (!raw) return [];

  const normalized = raw.replace(/\r\n/g, "\n");
  const hasTags = TAG_PATTERN.test(normalized);
  TAG_PATTERN.lastIndex = 0;

  if (!hasTags) return normalized.split("\n");

  let result = "";
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = TAG_PATTERN.exec(normalized)) !== null) {
    const tagIndex = match.index;
    const prefix = normalized.slice(lastIndex, tagIndex);

    if (prefix) {
      const lastNewline = prefix.lastIndexOf("\n");
      const tail = lastNewline === -1 ? prefix : prefix.slice(lastNewline + 1);
      if (tail.trim()) {
        result += prefix + "\n";
      } else {
        result += prefix;
      }
    }

    result += match[0];
    lastIndex = TAG_PATTERN.lastIndex;
  }

  result += normalized.slice(lastIndex);
  return result.split("\n");
}

export function buildExecutionLogs(
  raw: string,
  startType: ExecutionLog["type"] = "stdout",
): ExecutionLog[] {
  const lines = splitLogLines(String(raw ?? ""));
  const entries: ExecutionLog[] = [];
  // [FIX] Use deterministic timestamp to avoid hydration mismatch
  const now = 0;
  let currentType = startType;

  lines.forEach((line, idx) => {
    if (!line || !line.trim()) return;

    const tagMatch = line.match(/\[(STDOUT|STDERR|THOUGHT|RESULT|LOGS|SYSTEM)\]/);
    if (tagMatch) {
      const mappedType = TAG_TYPE_MAP[tagMatch[1]];
      if (mappedType) currentType = mappedType;
    }

    const content = line.replace(TAG_STRIP_PATTERN, "").trim();
    if (!content) return;

    entries.push({
      id: `log-${idx}`,
      timestamp: now,
      type: currentType,
      content,
    });
  });

  return entries;
}
