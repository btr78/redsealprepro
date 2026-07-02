import { ImageResponse } from "next/og";

export const alt = "RedSeal Prep Pro — Red Seal Practice Exams for 9 Trades with an AI Tutor";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px",
          background: "linear-gradient(135deg, #07090f 0%, #0e1118 60%, #131824 100%)",
          color: "#e8eaed",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 44 }}>
          <div
            style={{
              width: 72,
              height: 72,
              background: "linear-gradient(135deg, #ff6b35, #e65100)",
              borderRadius: 18,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              fontSize: 34,
              fontWeight: 900,
            }}
          >
            RS
          </div>
          <div style={{ display: "flex", fontSize: 40, fontWeight: 800 }}>
            RedSeal<span style={{ color: "#ff6b35" }}>Prep</span>
            <span style={{ color: "#9aa3b2", marginLeft: 14 }}>Pro</span>
          </div>
        </div>
        <div style={{ display: "flex", fontSize: 76, fontWeight: 900, lineHeight: 1.1, letterSpacing: -2 }}>
          Red Seal Practice Exams
        </div>
        <div style={{ display: "flex", fontSize: 38, color: "#9aa3b2", marginTop: 26 }}>
          9 Trades · 1,145+ Questions · AI Tutor
        </div>
        <div style={{ display: "flex", gap: 12, marginTop: 48 }}>
          {["Canada-wide", "Free to start", "Study on any device"].map((t) => (
            <div
              key={t}
              style={{
                display: "flex",
                background: "rgba(255,107,53,0.12)",
                border: "1px solid rgba(255,107,53,0.35)",
                borderRadius: 24,
                padding: "10px 24px",
                fontSize: 24,
                color: "#ffb08f",
              }}
            >
              {t}
            </div>
          ))}
        </div>
      </div>
    ),
    { ...size }
  );
}
