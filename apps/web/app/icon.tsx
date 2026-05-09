import { ImageResponse } from "next/og";

// Browser-tab favicon: bold lowercase "at" in pure black on a fully
// transparent background. Renders flat against whichever browser
// chrome the tab sits in. No rounded square, no plate, no colour —
// just the letterform.

export const runtime = "edge";
export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          background: "transparent",
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#000000",
        }}
      >
        <div
          style={{
            display: "flex",
            fontSize: 26,
            fontWeight: 900,
            letterSpacing: -2,
            lineHeight: 1,
          }}
        >
          at
        </div>
      </div>
    ),
    { ...size },
  );
}
