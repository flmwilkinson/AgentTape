import { ImageResponse } from "next/og";

// 180x180 home-screen icon. Same letterform-only treatment as the
// favicon — bold lowercase "at" in black on transparent. iOS will
// composite this over whatever the system shows behind app icons.

export const runtime = "edge";
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
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
            fontSize: 150,
            fontWeight: 900,
            letterSpacing: -10,
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
