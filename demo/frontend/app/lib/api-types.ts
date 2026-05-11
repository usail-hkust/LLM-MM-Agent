export * from "@/app/api/enums";
export * from "@/app/api/schemas";

// [FIX] Extended ExecutionArtifact interface to include physical storage capabilities
export interface ExecutionArtifact {
  id: string;
  name: string;
  type: string;
  data?: any; // Inline content (base64/text)
  url?: string; // Pre-signed or API URL
  blobHash?: string; // [NEW] CAS Physical Index for fallback loading
}
