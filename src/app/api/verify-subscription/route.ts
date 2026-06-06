import { NextRequest, NextResponse } from "next/server";
import { createHmac, timingSafeEqual } from "crypto";

const SECRET = process.env.ACTIVATION_SECRET!;
const CACHE_TTL = 24 * 60 * 60 * 1000;   // re-check Stripe after 24h
const MAX_AGE  = 30 * 24 * 60 * 60 * 1000; // hard-expire token after 30 days

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

    // ── Email verification path ────────────────────────────────
    if (!body.email || !String(body.email).includes("@")) {
      return NextResponse.json({ error: "Valid email required" }, { status: 400 });
    }
    const email = String(body.email).toLowerCase().trim();
    const { active, customerId } = await checkStripe(email);
    if (!active || !customerId) return NextResponse.json({ subscribed: false });
    const token = makeToken(email, customerId);
    return NextResponse.json({ subscribed: true, token, email });

  } catch (err) {
    console.error("verify-subscription error:", err);
    return NextResponse.json({ error: "Server error" }, { status: 500 });
  }
}
