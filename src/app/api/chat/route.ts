import { NextRequest, NextResponse } from "next/server";
import { createHmac, timingSafeEqual } from "crypto";

const MAX_AGE   = 30 * 24 * 60 * 60 * 1000;
const CACHE_TTL = 24 * 60 * 60 * 1000; // tokens older than this re-verify with Stripe

// ── Abuse limits (the AI tutor spends Anthropic tokens on our key) ──
// Rate limiting mirrors api/verify-subscription. A valid token is required to
// reach the model at all, but without these a subscriber (or a shared/leaked
// token, valid up to 24h post-cancel) could run unbounded / oversized calls.
const RL_WINDOW = 60_000;
const RL_LIMIT  = 15;              // AI messages per IP per minute (plenty for a human)
const MAX_MESSAGES     = 40;       // conversation turns accepted per request
const MAX_MSG_CHARS    = 4_000;    // per single message
const MAX_TOTAL_CHARS  = 16_000;   // summed across the conversation
const MAX_CONTEXT_CHARS = 4_000;   // questionContext blob cap

const hits = new Map<string, { n: number; t: number }>();
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

function parseToken(token: string): { email: string; iat: number } | null {
  try {
    const secret = process.env.ACTIVATION_SECRET;
    if (!secret) return null;
    const dot = token.lastIndexOf(".");
    if (dot < 0) return null;
    const payload = token.slice(0, dot);
    const sig     = token.slice(dot + 1);
    const expected = createHmac("sha256", secret).update(payload).digest("hex");
    const sigBuf = Buffer.from(sig,      "hex");
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

// Stale tokens must re-prove an active subscription — otherwise a cancelled
// subscriber could replay an old token here for the token's full 30-day life
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
      return NextResponse.json(
        { error: "Slow down — too many questions in a minute. Try again shortly." },
        { status: 429 }
      );
    }

    const { messages, questionContext, token, trade } = await req.json();

    const parsed = token ? parseToken(String(token)) : null;
    if (!parsed) {
      return NextResponse.json(
        { error: "Subscription required", code: "SUBSCRIBE" },
        { status: 401 }
      );
    }
    if (Date.now() - parsed.iat > CACHE_TTL && !(await stripeStillActive(parsed.email))) {
      return NextResponse.json(
        { error: "Subscription required", code: "SUBSCRIBE" },
        { status: 401 }
      );
    }

    // ── Input caps: reject oversized payloads before spending model tokens ──
    if (!Array.isArray(messages) || messages.length === 0) {
      return NextResponse.json({ error: "No messages provided" }, { status: 400 });
    }
    if (messages.length > MAX_MESSAGES) {
      return NextResponse.json({ error: "Conversation too long — start a new chat." }, { status: 413 });
    }
    let total = 0;
    for (const m of messages) {
      const t = typeof m?.text === "string" ? m.text : "";
      if (t.length > MAX_MSG_CHARS) {
        return NextResponse.json({ error: "Message too long." }, { status: 413 });
      }
      total += t.length;
    }
    if (total > MAX_TOTAL_CHARS) {
      return NextResponse.json({ error: "Conversation too long — start a new chat." }, { status: 413 });
    }
    const contextStr = questionContext
      ? JSON.stringify(questionContext).slice(0, MAX_CONTEXT_CHARS)
      : "";

    const tradeName = trade?.name ?? "433A Industrial Mechanic (Millwright)";
    const tradeId   = trade?.id   ?? "433A";

    const systemPrompt =
      `You are an expert Red Seal ${tradeId} ${tradeName} exam tutor. ` +
      `You help tradespeople prepare for the Certificate of Qualification exam. ` +
      `Be concise (2-3 paragraphs max), practical, and reference real-world shop floor scenarios. ` +
      `Use trade terminology naturally. If discussing a specific question, explain WHY each wrong ` +
      `answer is wrong, not just why the right one is right. Include exam tips when relevant.` +
      (contextStr ? `\n\nCurrent question context: ${contextStr}` : "");

    const resp = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": process.env.ANTHROPIC_API_KEY || "",
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-6",
        max_tokens: 1000,
        system: systemPrompt,
        messages: messages.map((m: { role: string; text: string }) => ({
          role: m.role === "ai" ? "assistant" : m.role,
          content: m.text,
        })),
      }),
    });

    const data = await resp.json();
    const text =
      data.content?.map((c: { text?: string }) => c.text || "").join("") ||
      "Sorry, I couldn't process that. Please try again.";

    return NextResponse.json({ text });
  } catch (error) {
    console.error("Chat API error:", error);
    return NextResponse.json({ text: "Connection issue. Please try again." }, { status: 500 });
  }
}
