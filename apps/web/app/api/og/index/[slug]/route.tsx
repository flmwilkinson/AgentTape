import { ImageResponse } from "next/og";
import { api } from "@/lib/api-client";

// Route handler exports — Next.js 15 only allows ``runtime`` here. The
// ImageResponse below sets the content-type + size on the response.
export const runtime = "edge";

const SIZE = { width: 1200, height: 630 };

interface RouteParams {
  params: Promise<{ slug: string }>;
}

export async function GET(_req: Request, { params }: RouteParams) {
  const { slug } = await params;
  let detail;
  try {
    detail = await api.getIndex(slug);
  } catch {
    return new Response("not found", { status: 404 });
  }
  const history = await api
    .indexHistory(slug, "30d")
    .catch(() => [])
    .then((rows) => rows.map((r) => r.composite_value));
  const composite = detail.composite_value;

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
            color: "#8b8e96",
            fontSize: 18,
            letterSpacing: 4,
            textTransform: "uppercase",
          }}
        >
          {`AgentTape · Index · ${detail.rebalance_frequency}`}
        </div>
        <div style={{ display: "flex", marginTop: 24, fontSize: 128, fontWeight: 600, letterSpacing: -3, lineHeight: 1.05 }}>
          {detail.name}
        </div>
        <div style={{ marginTop: "auto", display: "flex", alignItems: "flex-end", gap: 32 }}>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div style={{ color: "#8b8e96", fontSize: 16, letterSpacing: 4, textTransform: "uppercase" }}>
              Composite
            </div>
            <div
              style={{
                fontSize: 200,
                fontWeight: 700,
                letterSpacing: -5,
                lineHeight: 1,
                color: "#3b82f6",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {composite === null ? "—" : composite.toFixed(1)}
            </div>
            <div style={{ display: "flex", color: "#8b8e96", fontSize: 18, marginTop: 8 }}>
              {`${detail.members_count} constituents`}
            </div>
          </div>
          <SparklineSvg values={history} />
        </div>
      </div>
    ),
    SIZE,
  );
}

function SparklineSvg({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  const w = 540;
  const h = 220;
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
