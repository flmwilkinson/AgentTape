export default function Home() {
  return (
    <main className="container mx-auto flex min-h-screen flex-col items-center justify-center gap-6 px-4 py-16">
      <div className="text-xs uppercase tracking-widest text-muted-foreground">
        AgentTape
      </div>
      <h1 className="text-4xl font-semibold tracking-tight md:text-6xl">
        The live tape for AI agents.
      </h1>
      <p className="max-w-xl text-center text-muted-foreground">
        No seed list. Discovery scans GitHub, Hugging Face, MCP registries,
        package managers, arXiv, and Hacker News. Signals tick into the index
        in near real-time.
      </p>
    </main>
  );
}
