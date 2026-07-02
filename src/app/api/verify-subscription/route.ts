import { NextRequest, NextResponse } from "next/server";
import { createHmac, timingSafeEqual } from "crypto";

const SECRET = process.env.ACTIVATION_SECRET!;
const CACHE_TTL = 24 * 60 * 60 * 1000;   // re-check Stripe after 24h
const MAX_AGE  = 30 * 24 * 60 * 60 * 1000; // hard-expire token after 30 days

// ── Rate limiting (in-memory; Fluid Compute reuses instances) ──
const hits = new Map<string, { n: number; t: number }>();
const RL_WINDOW = 60_000;
const RL_LIMIT  = 10;

function rateLimited(ip: string): boolean {
  const now = Date.now();
  if (hits.size > 5000) {
    for (const [k, v] of hits) if (now - v.t > RL_WINDOW) hits.delete(k);
  }
  const h = hits.get(ip);
  if (!h || now - h.t > RL_WINDOW) { hits.set(ip, { n: 1, t: now }); return false; }
  h.n++;
  return h.n > RL_LIMIT;
}

function sign(data: string): string {
  return createHmac("sha256", SECRET).update(data).digest("hex");
}

function makeToken(email: string, customerId: string): string {
  const payload = Buffer.from(JSON.stringify({ email, customerId, iat: Date.now() })).toString("base64url");
  return `${payload}.${sign(payload)}`;
}

function parseToken(token: string): { email: string; customerId: string; iat: number } | null {
  try {
    const dot = token.lastIndexOf(".");
    if (dot < 0) return null;
    const payload = token.slice(0, dot);
    const sig     = token.slice(dot + 1);
    const expected = sign(payload);
    // Reject if lengths differ (malformed token) or signature mismatch
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

// Resolve a Supabase session token to its verified email — proof the caller owns the address
async function supabaseEmail(accessToken: string): Promise<string | null> {
  const url  = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anon) return null;
  try {
    const res = await fetch(`${url}/auth/v1/user`, {
      headers: { apikey: anon, Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) return null;
    const user = await res.json();
    return user?.email ? String(user.email).toLowerCase() : null;
  } catch {
    return null;
  }
}

async function checkStripe(email: string): Promise<{ active: boolean; customerId?: string }> {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) return { active: false };

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
    const hasActive = (subData.data ?? []).some(
      (s: { status: string }) => s.status === "active" || s.status === "trialing"
    );
    if (hasActive) return { active: true, customerId: cus.id };
  }
  return { active: false };
}

export async function POST(req: NextRequest) {
  try {
    const ip = (req.headers.get("x-forwarded-for") ?? "unknown").split(",")[0].trim();
    if (rateLimited(ip)) {
      return NextResponse.json({ error: "Too many attempts — try again in a minute" }, { status: 429 });
    }

    const body = await req.json();

    // ── Token refresh path ─────────────────────────────────────
    if (body.token) {
      const parsed = parseToken(body.token);
      if (!parsed) return NextResponse.json({ subscribed: false });

      const age = Date.now() - parsed.iat;
      if (age < CACHE_TTL) {
        // Fresh token — trust without hitting Stripe
        return NextResponse.json({ subscribed: true, token: body.token, email: parsed.email });
      }

      // Stale — re-verify live with Stripe
      const { active, customerId } = await checkStripe(parsed.email);
      if (!active) return NextResponse.json({ subscribed: false });
      const newToken = makeToken(parsed.email, customerId ?? parsed.customerId);
      return NextResponse.json({ subscribed: true, token: newToken, email: parsed.email });
    }

    // ── Activation path — requires a signed-in Supabase session ──
    // (a bare email is NOT accepted: it would let anyone mint a token
    //  with a subscriber's address without proving they own it)
    if (body.supabaseToken) {
      const email = await supabaseEmail(String(body.supabaseToken));
      if (!email) {
        return NextResponse.json({ error: "Sign-in expired — please sign in again", code: "SIGNIN" }, { status: 401 });
      }
      const { active, customerId } = await checkStripe(email);
      if (!active || !customerId) return NextResponse.json({ subscribed: false, email });
      return NextResponse.json({ subscribed: true, token: makeToken(email, customerId), email });
    }

    return NextResponse.json({ error: "Sign-in required", code: "SIGNIN" }, { status: 401 });

  } catch (err) {
    console.error("verify-subscription error:", err);
    return NextResponse.json({ error: "Server error" }, { status: 500 });
  }
}
