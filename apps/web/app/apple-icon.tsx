import { ImageResponse } from "next/og";

// 180x180 icon used by iOS / iPadOS when AgentTape is added to a
// home screen. Same design language as the favicon: black square,
// white serif "AT", no decoration. Scale of 180 lets the typography
// breathe and stay crisp on Retina.

export const runtime = "edge";
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
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
            fontSize: 122,
            fontWeight: 700,
            letterSpacing: -8,
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
