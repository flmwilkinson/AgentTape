// Single source of truth for capability / deployment taxonomy used by
// the homepage chips, /trending filters, the capability rail, etc.
// Adding or reordering anything here is a one-line change that
// propagates to every page that surfaces these axes — so a returning
// user sees the same options in the same order regardless of where
// they entered the app.

export type TaxonomyEntry = { slug: string; label: string };

// Capabilities — what the agent does. Order is the order chips render
// in. Pick a sensible "the user is most likely to want this" ranking.
export const CAPABILITIES: TaxonomyEntry[] = [
  { slug: "code-generation", label: "Coding" },
  { slug: "browsing", label: "Browser" },
  { slug: "research", label: "Research" },
  { slug: "rag", label: "RAG" },
  { slug: "multi-agent", label: "Multi-agent" },
  { slug: "automation", label: "Automation" },
  { slug: "tool-use", label: "Tool use" },
  { slug: "memory", label: "Memory" },
  { slug: "vision", label: "Vision" },
  { slug: "voice", label: "Voice" },
];

// Deployment shapes — how you run the agent.
export const DEPLOYMENTS: TaxonomyEntry[] = [
  { slug: "library", label: "Library" },
  { slug: "cli", label: "CLI" },
  { slug: "saas", label: "SaaS" },
  { slug: "ide-plugin", label: "IDE plugin" },
  { slug: "browser-extension", label: "Browser ext" },
  { slug: "mcp-server", label: "MCP" },
];
