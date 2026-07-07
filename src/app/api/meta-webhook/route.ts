import { NextRequest, NextResponse } from "next/server";
import { createHmac, timingSafeEqual } from "crypto";

// Meta calls this route directly over HTTPS (it's the registered webhook
// callback URL in the Meta App dashboard). We verify Meta's signature, then
// forward the raw event to the marketing-crew community_manager.py Flask
// server on the droplet, which does the actual classification/reply/lead
// handling. Mirrors the verification pattern in api/stripe/webhook/route.ts.

function verifyMetaSignature(body: string, header: string | null, appSecret: string): boolean {
  if (!header) return false;
  try {
    const [scheme, sig] = header.split("=");
    if (scheme !== "sha256" || !sig) return false;
    const expected = createHmac("sha256", appSecret).update(body).digest("hex");
    const expBuf = Buffer.from(expected, "hex");
    const sigBuf = Buffer.from(sig, "hex");
    if (expBuf.length !== sigBuf.length) return false;
    return timingSafeEqual(expBuf, sigBuf);
  } catch {
    return false;
  }
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const mode = searchParams.get("hub.mode");
  const token = searchParams.get("hub.verify_token");
  const challenge = searchParams.get("hub.challenge");

  const verifyToken = process.env.META_VERIFY_TOKEN ?? "";
  if (mode === "subscribe" && verifyToken && token === verifyToken && challenge) {
    return new NextResponse(challenge, { status: 200 });
  }
  return NextResponse.json({ error: "verification failed" }, { status: 403 });
}

export async function POST(req: NextRequest) {
  const body = await req.text();
  const signature = req.headers.get("x-hub-signature-256");
  const appSecret = process.env.META_APP_SECRET ?? "";

  if (!appSecret) {
    console.error("META_APP_SECRET not configured");
    return NextResponse.json({ error: "Not configured" }, { status: 500 });
  }
  if (!verifyMetaSignature(body, signature, appSecret)) {
    console.error("Invalid Meta webhook signature");
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  // Best-effort forward to the droplet; Meta needs a fast 200 regardless, and
  // retries on non-200s, so a slow/down droplet shouldn't make Meta hammer us.
  const dropletUrl = process.env.MARKETING_DROPLET_WEBHOOK_URL;
  const relaySecret = process.env.MARKETING_RELAY_SECRET;
  if (dropletUrl && relaySecret) {
    try {
      await fetch(dropletUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Relay-Secret": relaySecret },
        body,
        signal: AbortSignal.timeout(4000),
      });
    } catch (e) {
      console.error("Forward to droplet failed:", e);
    }
  } else {
    console.error("MARKETING_DROPLET_WEBHOOK_URL or MARKETING_RELAY_SECRET not configured");
  }

  return NextResponse.json({ received: true });
}
