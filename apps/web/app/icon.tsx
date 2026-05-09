import { ImageResponse } from "next/og";

// Browser-tab favicon. Monochrome by design: black square, white
// serif "AT". Keeping it letterform-only (no colour, no rounded
// corners, no decorative motif) reads more editorial / less app-y at
// 16x16, which is where most users will see it.

export const runtime = "edge";
export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          background: "#0a0a0a",
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "white",
        }}
      >
        <div
          style={{
            display: "flex",
            fontSize: 22,
            fontWeight: 700,
            letterSpacing: -2,
            // System serif stack the edge runtime can resolve. No
            // custom font fetch on every request — keeps cold-start
            // cheap.
            fontFamily: "ui-serif, Georgia, 'Times New Roman', serif",
            lineHeight: 1,
          }}
        >
          AT
        </div>
      </div>
    ),
    { ...size },
  );
}
