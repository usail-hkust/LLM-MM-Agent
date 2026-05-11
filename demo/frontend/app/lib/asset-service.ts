/**
 * Asset Service
 * Handles asset-related storage operations
 */
export const assetService = {
  /**
   * Clear asset-related data from storage
   * Note: Authentication tokens are handled by AuthContext via the auth:unauthorized event
   */
  clear: () => {
    // Clear any asset-related localStorage items if needed
    // Currently, authentication is handled by AuthContext
    // This method is kept for compatibility with api-client.ts
    if (typeof window !== "undefined") {
      // Add any asset-specific cleanup here if needed in the future
      // For now, this is a no-op since AuthContext handles token clearing
    }
  },
};
