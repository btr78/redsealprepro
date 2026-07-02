// One dynamic route → 9 statically-generated, keyword-targeted Red Seal landing pages.
import { TRADES_SEO, findTrade } from "../trades-seo";

export const dynamicParams = false; // only the 9 trade slugs are valid routes; anything else 404s

export function generateStaticParams() {
  return TRADES_SEO.map((t) => ({ trade: t.slug }));
}

export async function generateMetadata({ params }) {
  const { trade } = await params;
  const t = findTrade(trade);
  if (!t) return {};
  const title = `${t.name} (${t.code}) Red Seal Practice Exam — Free Practice Questions | RedSeal Prep Pro`;
  const description = `${t.intro} Try free practice questions for the ${t.code} Certificate of Qualification with an AI tutor that explains every answer.`;
  const url = `https://www.redsealprep.pro/${t.slug}`;
  return {
    title, description,
    alternates: { canonical: url },
    openGraph: { title, description, url, type: "website", siteName: "RedSeal Prep Pro" },
    twitter: { card: "summary_large_image", title, description },
  };
}

const C = { bg: "#07090f", bg2: "#0e1118", border: "#1c2230", text: "#e8eaed", text2: "#9aa3b2", accent: "#ff6b35" };
const wrap = { maxWidth: 820, margin: "0 auto", padding: "0 20px" };

export default async function TradeLanding({ params }) {
  const { trade } = await params;
  const t = findTrade(trade);
  if (!t) return null;
  const others = TRADES_SEO.filter((x) => x.slug !== t.slug);
  return (
    <main style={{ fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif", background: C.bg, color: C.text, minHeight: "100vh" }}>
      <nav style={{ ...wrap, maxWidth: 1100, display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px 20px", borderBottom: `1px solid ${C.border}` }}>
        <a href="/" style={{ display: "flex", alignItems: "center", gap: 8, textDecoration: "none", color: C.text }}>
          <span style={{ width: 30, height: 30, background: `linear-gradient(135deg, ${C.accent}, #e65100)`, borderRadius: 8, display: "inline-flex", alignItems: "center", justifyContent: "center" }}>⚙️</span>
          <b>RedSeal<span style={{ color: C.accent }}>Prep</span></b>
        </a>
        <a href="/" style={{ background: C.accent, color: "#fff", padding: "9px 18px", borderRadius: 8, fontWeight: 700, fontSize: 13, textDecoration: "none" }}>Start Free →</a>
      </nav>

      <article style={{ ...wrap, padding: "48px 20px 24px" }}>
        <div style={{ display: "inline-block", background: "rgba(255,107,53,0.1)", border: "1px solid rgba(255,107,53,0.25)", borderRadius: 20, padding: "5px 14px", fontSize: 12, color: C.accent, fontWeight: 600, marginBottom: 18 }}>
          🇨🇦 RED SEAL · {t.code}
        </div>
        <h1 style={{ fontSize: "clamp(1.8rem, 5vw, 2.8rem)", fontWeight: 900, lineHeight: 1.15, letterSpacing: "-1px", margin: "0 0 16px" }}>
          {t.name} ({t.code}) Red Seal Practice Exam
        </h1>
        <p style={{ fontSize: "1.1rem", color: C.text2, lineHeight: 1.7, maxWidth: 640, margin: "0 0 28px" }}>{t.intro}</p>
        <a href="/" style={{ display: "inline-block", background: C.accent, color: "#fff", padding: "15px 30px", borderRadius: 10, fontWeight: 800, fontSize: 16, textDecoration: "none" }}>
          Start Free {t.short} Practice →
        </a>
        <p style={{ color: C.text2, fontSize: 13, marginTop: 14 }}>No credit card to start · AI tutor explains every answer · Study on any device</p>
      </article>

      <section style={{ ...wrap, padding: "16px 20px 40px" }}>
        <h2 style={{ fontSize: "1.5rem", fontWeight: 800, margin: "24px 0 16px" }}>What&apos;s on the {t.short} Red Seal exam</h2>
        <ul style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 10, listStyle: "none", padding: 0, margin: 0 }}>
          {t.topics.map((topic) => (
            <li key={topic} style={{ background: C.bg2, border: `1px solid ${C.border}`, borderRadius: 10, padding: "14px 16px", fontSize: 15 }}>✓ {topic}</li>
          ))}
        </ul>

        <h2 style={{ fontSize: "1.5rem", fontWeight: 800, margin: "40px 0 12px" }}>Why study with RedSeal Prep Pro</h2>
        <p style={{ color: C.text2, lineHeight: 1.7, maxWidth: 640 }}>
          Realistic {t.code} questions written in the style of the real Certificate of Qualification, randomized so you actually learn the material (not the answer pattern). Every question comes with a plain-English explanation, plus an AI tutor you can ask “why?”. Track your weak categories, build a study streak, and sign in to pick up where you left off on any device.
        </p>
        <div style={{ marginTop: 24 }}>
          <a href="/" style={{ display: "inline-block", background: C.accent, color: "#fff", padding: "15px 30px", borderRadius: 10, fontWeight: 800, fontSize: 16, textDecoration: "none" }}>
            Try {t.short} Practice Questions →
          </a>
        </div>

        <h2 style={{ fontSize: "1.2rem", fontWeight: 800, margin: "44px 0 12px" }}>Other Red Seal trades</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {others.map((o) => (
            <a key={o.slug} href={`/${o.slug}`} style={{ color: C.text2, background: C.bg2, border: `1px solid ${C.border}`, borderRadius: 8, padding: "8px 12px", fontSize: 13, textDecoration: "none" }}>
              {o.name} ({o.code})
            </a>
          ))}
        </div>
      </section>

      <footer style={{ ...wrap, maxWidth: 1100, borderTop: `1px solid ${C.border}`, padding: "24px 20px", color: C.text2, fontSize: 13, display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <span>© {new Date().getFullYear()} RedSeal Prep Pro</span>
        <span><a href="/privacy" style={{ color: C.text2 }}>Privacy</a> · <a href="/terms" style={{ color: C.text2 }}>Terms</a></span>
      </footer>
    </main>
  );
}
