// One-line plain-language summary per index slug. Surfaces alongside
// the ticker on cards and on the index detail page so a first-time
// reader knows what each basket is for without clicking through.
//
// Keep these short and concrete (under ~70 chars each) — they sit
// next to the ticker name on space-constrained cards. Detailed
// methodology lives on /methodology and on the per-index page.

export const INDEX_SUMMARIES: Record<string, string> = {
  "tape-100":
    "Top 100 agents and models across the whole index, by AgentScore.",
  "code-25": "Top 25 coding agents — write code, review PRs, ship features.",
  "web-25": "Top 25 browser agents — drive a real browser to do tasks.",
  "oss-50": "Top 50 open-source agents — permissive licence, public repo.",
  "mcp-25": "Top 25 MCP servers — tools, sources and surfaces for agents.",
  "fm-50":
    "Top 50 foundation models — the LLMs powering everything above.",
};
