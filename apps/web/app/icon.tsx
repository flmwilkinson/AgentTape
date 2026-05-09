import { ImageResponse } from "next/og";

// Browser-tab favicon. Next.js compiles this file into the small
// (32x32) icon served at /icon. The brand mark is "AT" set in mono,
// reversed out of the deep electric blue accent so the favicon
// reads at a glance even when the tab favicon strip is crowded.

export const runtime = "edge";
export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          fontSize: 20,
          background: "#1547e6",
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "white",
          fontWeight: 700,
          fontFamily: "monospace",
          letterSpacing: -1,
        }}
      >
        AT
      </div>
    ),
    { ...size },
  );
}
