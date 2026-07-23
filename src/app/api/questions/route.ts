import { NextRequest, NextResponse } from "next/server";
import { createHmac, timingSafeEqual } from "crypto";
import { selectQuestions, TRADE_IDS } from "../../data/questionBanks";

// Gated question delivery. Without this, the whole bank shipped in the client
// bundle (any visitor could download all 1,320+ Q&A). Now:
//  - anonymous / unpaid  -> only the public ~20-question sample pool per trade
//  - valid paid token    -> the full bank, per session, mode-selected server-side
// Answers reach the browser only for the current session's questions (needed to
// grade); nobody can pull the entire library in one request anymore.

const MAX_AGE   = 30 * 24 * 60 * 60 * 1000;
const CACHE_TTL = 24 * 60 * 60 * 1000; // tokens older than this re-verify with Stripe

// ── Abuse limits (Phase 2) ──
const RL_WINDOW = 60_000;
const RL_LIMIT  = 40;          // requests per IP per minute (a session starts a few)
const DAILY_Q_CEILING = 3000;  // questions/identity/day — real study is a few hundred

const hits = new Map<string, { n: number; t: number }>();
function rateLimited(ip: string): boolean {
  const now = Date.now();
  if (hits.size > 5000) for (const [k, v] of hits) if (now - v.t > RL_WINDOW) hits.delete(k);
  const h = hits.get(ip);
  if (!h || now - h.t > RL_WINDOW) { hits.set(ip, { n: 1, t: now }); return false; }
  h.n++;
  return h.n > RL_LIMIT;
}

// Per-identity daily question ceiling — stops one paid login from vacuuming the
// whole library across many requests. Keyed by token (falls back to IP).
const served = new Map<string, { n: number; day: string }>();
function overDailyCeiling(key: string, add: number): boolean {
  const day = new Date().toISOString().slice(0, 10);
  if (served.size > 20000) for (const [k, v] of served) if (v.day !== day) served.delete(k);
  const s = served.get(key);
  if (!s || s.day !== day) { served.set(key, { n: add, day }); return false; }
  s.n += add;
  return s.n > DAILY_Q_CEILING;
}

function parseToken(token: string): { email: string; iat: number } | null {
  try {
    const secret = process.env.ACTIVATION_SECRET;
    if (!secret) return null;
    const dot = token.lastIndexOf(".");
    if (dot < 0) return null;
    const payload = token.slice(0, dot);
    const sig = token.slice(dot + 1);
    const expected = createHmac("sha256", secret).update(payload).digest("hex");
    const sigBuf = Buffer.from(sig, "hex");
    const expBuf = Buffer.from(expected, "hex");
    if (sigBuf.length !== expBuf.length) return null;
    if (!timingSafeEqual(sigBuf, expBuf)) return null;
    const data = JSON.parse(Buffer.from(payload, "base64url").toString());
    if (Date.now() - data.iat > MAX_AGE) return null;
    return data;
  } catch {
    return null;
  }
}

async function stripeStillActive(email: string): Promise<boolean> {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) return false;
  const cusRes = await fetch(
    `https://api.stripe.com/v1/customers?email=${encodeURIComponent(email)}&limit=5`,
    { headers: { Authorization: `Bearer ${key}` } }
  );
  const cusData = await cusRes.json();
  for (const cus of (cusData.data ?? [])) {
    const subRes = await fetch(
      `https://api.stripe.com/v1/subscriptions?customer=${cus.id}&limit=10`,
      { headers: { Authorization: `Bearer ${key}` } }
    );
    const subData = await subRes.json();
    if ((subData.data ?? []).some(
      (s: { status: string }) => s.status === "active" || s.status === "trialing"
    )) return true;
  }
  return false;
}

export async function POST(req: NextRequest) {
  try {
    const ip = (req.headers.get("x-forwarded-for") ?? "unknown").split(",")[0].trim();
    if (rateLimited(ip)) {
      return NextResponse.json({ error: "Too many requests — try again shortly." }, { status: 429 });
    }

    const body = await req.json();
    const trade = String(body.trade ?? "");
    const mode  = String(body.mode ?? "practice");
    const cat   = body.cat != null ? String(body.cat) : undefined;
    const ids   = Array.isArray(body.ids) ? body.ids.slice(0, 2000) : undefined;
    const examCount = Number.isFinite(body.examCount) ? Math.min(Number(body.examCount), 400) : undefined;
    const token = body.token ? String(body.token) : null;

    if (!TRADE_IDS.includes(trade)) {
      return NextResponse.json({ error: "Unknown trade" }, { status: 400 });
    }

    // Entitlement: valid fresh token, or stale token that re-proves an active sub.
    const parsed = token ? parseToken(token) : null;
    let entitled = false;
    if (parsed) {
      entitled = (Date.now() - parsed.iat <= CACHE_TTL) || (await stripeStillActive(parsed.email));
    }

    const questions = selectQuestions({ trade, mode, cat, ids, entitled, examCount });

    // Daily ceiling only matters for entitled callers (free is already tiny/public).
    if (entitled) {
      const key = parsed ? `t:${parsed.email}` : `ip:${ip}`;
      if (overDailyCeiling(key, questions.length)) {
        return NextResponse.json(
          { error: "Daily practice limit reached — take a break and come back tomorrow." },
          { status: 429 }
        );
      }
    }

    return NextResponse.json({ questions, entitled });
  } catch (err) {
    console.error("questions API error:", err);
    return NextResponse.json({ error: "Server error" }, { status: 500 });
  }
}
