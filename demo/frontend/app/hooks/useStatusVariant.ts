import { useMemo } from "react";
import { resolveStatusIdentity } from "@/app/lib/status-engine";

type StatusVariantInput =
  | string
  | {
      status?: string;
      statusOverride?: "RUNNING" | "AWAITING_HUMAN_INPUT" | "FAILED";
      isPendingAction?: boolean;
      actorType?: "bot" | "user";
      [key: string]: unknown;
    };

function toResolverParams(input?: StatusVariantInput) {
  if (!input || typeof input === "string") {
    return { status: input };
  }
  const { status, statusOverride, isPendingAction, actorType } = input;
  return { status, statusOverride, isPendingAction, actorType };
}

export function getStatusVariant(input?: StatusVariantInput) {
  const config = resolveStatusIdentity(toResolverParams(input));
  return {
    ...config,
    color: config.theme.text,
    bgColor: config.theme.bg,
    borderColor: config.theme.border,
    animate: !!config.animation, // Backward compatibility for boolean animation
  };
}

export function useStatusVariant(input?: StatusVariantInput) {
  return useMemo(() => getStatusVariant(input), [input]);
}
