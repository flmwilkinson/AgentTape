import { api } from "@/lib/api-client";

interface RouteParams {
  params: Promise<{ slug: string }>;
}

// "Show Your Work": stream the agent's signals as a CSV. The frontend
// just shapes the upstream JSON as text/csv — apps/api owns the data.
export async function GET(req: Request, { params }: RouteParams) {
  const { slug } = await params;
  const url = new URL(req.url);
  const window = url.searchParams.get("window") ?? "30d";
  let series;
  try {
    series = await api.agentSignals(slug, { window });
  } catch (e) {
    return new Response("not found", { status: 404 });
  }
  const lines = ["source,captured_at,value"];
  for (const s of series) {
    for (const p of s.points) {
      lines.push(`${s.source},${p.captured_at},${p.value}`);
    }
  }
  return new Response(lines.join("\n"), {
    headers: {
      "content-type": "text/csv; charset=utf-8",
      "content-disposition": `attachment; filename="${slug}-signals-${window}.csv"`,
    },
  });
}
