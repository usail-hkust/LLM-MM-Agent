"use client";
import { createContext, useContext } from "react";
const NodeContext = createContext<{ projectId: string; nodeId: string | null; isReadOnly: boolean } | null>(null);
export const useNodeContext = () => useContext(NodeContext)!;
export const NodeProvider = NodeContext.Provider;
