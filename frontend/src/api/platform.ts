// Re-export hub — all existing imports from "../api/platform" continue to work.
// Core: api/core.ts (axios instance, auth interceptors, token management, ws url helper)
// Domain: api/domain.ts (all domain types + API call functions)

export * from "./core";
export * from "./domain";
