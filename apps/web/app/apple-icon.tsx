import { ImageResponse } from "next/og";

// 180x180 icon used by iOS / iPadOS when a user adds AgentTape to
// their home screen. Same brand mark as the favicon, scaled up so
// the typography stays crisp at app-icon size on Retina displays.

export const runtime = "edge";
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          fontSize: 110,
          background: "#1547e6",
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "white",
          fontWeight: 700,
          fontFamily: "monospace",
          letterSpacing: -3,
        }}
      >
        AT
      </div>
    ),
    { ...size },
  );
}
