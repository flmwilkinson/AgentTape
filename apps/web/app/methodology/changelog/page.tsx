import { execSync } from "node:child_process";
import path from "node:path";
import Link from "next/link";

export const metadata = {
  title: "Methodology changelog — AgentTape",
  description:
    "Every change to how AgentScore is computed, indexes are rebalanced, and signals are weighted. Sourced from git history.",
};

// Sourced live from git so this is impossible to fake. Each entry maps
// to a commit that touched a methodology-defining file: the scoring
// engine, the index catalog, the pillar weights config, or the public
// methodology page itself.

interface Entry {
  hash: string;
  isoDate: string;
  author: string;
  subject: string;
  url: string;
}

const TRACKED_PATHS = [
  "apps/scoring/src/scoring/compute.py",
  "apps/scoring/src/scoring/indexes.py",
  "apps/scoring/src/scoring/config.py",
  "apps/web/app/methodology",
];

function loadEntries(): Entry[] {
  // Walk the repo root from this file's location. The page is under
  // apps/web/app/methodology/changelog, so four ".." steps reach the
  // workspace root.
  const repoRoot = path.resolve(process.cwd(), "..", "..");
  try {
    const out = execSync(
      `git log --pretty=format:"%H|%ai|%an|%s" -- ${TRACKED_PATHS.join(" ")}`,
      { cwd: repoRoot, encoding: "utf8", maxBuffer: 4 * 1024 * 1024 },
    );
    const repoUrl = "https://github.com/flmwilkinson/AgentTape";
    return out
      .split("\n")
      .filter(Boolean)
      .map((line) => {
        const [hash, isoDate, author, ...rest] = line.split("|");
        return {
          hash,
          isoDate,
          author,
          subject: rest.join("|"),
          url: `${repoUrl}/commit/${hash}`,
        };
      });
  } catch {
    return [];
  }
}

export default function MethodologyChangelogPage() {
  const entries = loadEntries();
  return (
    <article className="container py-12 md:py-16 max-w-3xl">
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        Methodology · changelog
      </div>
      <h1 className="editorial mt-3 text-3xl font-semibold leading-tight md:text-4xl">
        Every change is a commit.
      </h1>
      <p className="mt-4 max-w-2xl text-base text-muted-foreground">
        Pillar weights, scoring rules, index definitions and the public
        methodology page live in the open repository. This list is generated
        from{" "}
        <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
          git log
        </code>{" "}
        at build time — there is no separate "changelog file" we could
        forget to update.
      </p>
      <p className="mt-2 text-sm text-muted-foreground">
        Read the live{" "}
        <Link href="/methodology" className="text-primary hover:underline">
          methodology page
        </Link>
        .
      </p>

      <ol className="mt-10 space-y-3">
        {entries.length === 0 && (
          <li className="rounded-md border border-dashed border-border bg-card px-4 py-6 text-sm text-muted-foreground">
            Build server has no git history available. Once deployed
            from a git checkout this list populates automatically.
          </li>
        )}
        {entries.map((e) => (
          <li
            key={e.hash}
            className="rounded-md border border-border bg-card px-4 py-3"
          >
            <div className="flex flex-wrap items-baseline gap-3 text-xs text-muted-foreground">
              <a
                href={e.url}
                target="_blank"
                rel="noreferrer"
                className="font-mono text-primary hover:underline"
              >
                {e.hash.slice(0, 7)}
              </a>
              <span className="font-mono">
                {new Date(e.isoDate).toLocaleDateString(undefined, {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                })}
              </span>
              <span>·</span>
              <span>{e.author}</span>
            </div>
            <div className="mt-1 text-sm text-foreground/90">{e.subject}</div>
          </li>
        ))}
      </ol>
    </article>
  );
}
