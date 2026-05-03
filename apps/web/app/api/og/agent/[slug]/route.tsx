import { ImageResponse } from "next/og";
import { api } from "@/lib/api-client";

export const runtime = "edge";

const SIZE = { width: 1200, height: 630 };

interface RouteParams {
  params: Promise<{ slug: string }>;
}

export async function GET(_req: Request, { params }: RouteParams) {
  const { slug } = await params;
  let agent;
  try {
    agent = await api.getAgent(slug);
  } catch {
    return new Response("not found", { status: 404 });
  }

  // Pull a tiny history for the sparkline.
  const stars = await api
    .agentSignals(slug, { sources: ["github_stars"], window: "30d" })
    .then((s) => s[0]?.points ?? [])
    .catch(() => []);
  const values = stars.map((p) => p.value);
  const score = agent.score?.agent_score ?? null;

  return new ImageResponse(
    (
      <div
        style={{
          background: "#0b0c10",
          color: "#f4f4f5",
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          padding: "64px 72px",
          fontFamily: "Inter, system-ui",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            color: "#8b8e96",
            fontSize: 18,
            letterSpacing: 4,
            textTransform: "uppercase",
          }}
        >
          {`AgentTape · ${agent.discovered_via.replace(/_/g, " ")}`}
        </div>
        <div style={{ display: "flex", marginTop: 24, fontSize: 96, fontWeight: 600, letterSpacing: -2, lineHeight: 1.05 }}>
          {agent.name}
        </div>
        {agent.description && (
          <div
            style={{
              marginTop: 16,
              fontSize: 28,
              color: "#b6b8be",
              maxWidth: 1000,
              lineHeight: 1.35,
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {agent.description}
          </div>
        )}
        <div style={{ marginTop: "auto", display: "flex", alignItems: "flex-end", gap: 32 }}>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div style={{ color: "#8b8e96", fontSize: 16, letterSpacing: 4, textTransform: "uppercase" }}>
              AgentScore
            </div>
            <div
              style={{
                fontSize: 160,
                fontWeight: 700,
                letterSpacing: -4,
                lineHeight: 1,
                color: "#3b82f6",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {score === null ? "—" : score.toFixed(1)}
            </div>
          </div>
          <SparklineSvg values={values} />
        </div>
      </div>
    ),
    SIZE,
  );
}

function SparklineSvg({ values }: { values: number[] }) {
  if (values.length < 2) {
    return (
      <div
        style={{
          marginLeft: "auto",
          color: "#8b8e96",
          fontSize: 14,
          textTransform: "uppercase",
          letterSpacing: 4,
        }}
      >
        no series yet
      </div>
    );
  }
  const w = 600;
  const h = 200;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const stepX = w / (values.length - 1);
  const path = values
    .map((v, i) => {
      const x = i * stepX;
      const y = h - ((v - min) / range) * h;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg width={w} height={h} style={{ marginLeft: "auto" }}>
      <path d={path} stroke="#3b82f6" strokeWidth={3} fill="none" strokeLinejoin="round" />
    </svg>
  );
}
