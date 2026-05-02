// Generated TS types from the AgentTape OpenAPI spec will land here.
// Until the API publishes its schema, we declare a small placeholder so
// downstream packages can import from "@agenttape/shared" without breaking.

export type IngestionTier = "fast" | "medium" | "slow";

export interface AgentSummary {
  id: string;
  name: string;
  source: "github" | "huggingface" | "mcp" | "package" | "arxiv" | "hn";
  admittedAt: string;
  score: number;
}

export interface TickEvent {
  agentId: string;
  signal: string;
  value: number;
  at: string;
}
