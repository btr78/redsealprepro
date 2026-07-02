import { NextRequest, NextResponse } from "next/server";
import { createHmac, timingSafeEqual } from "crypto";

function verifyStripeSignature(body: string, header: string, secret: string): boolean {
  try {
    const parts: Record<string, string> = {};
    header.split(",").forEach(p => { const [k, v] = p.split("="); parts[k] = v; });
    const { t, v1 } = parts;
    if (!t || !v1) return false;

    // Reject events older than 5 minutes (replay attack prevention)
    if (Math.abs(Date.now() / 1000 - Number(t)) > 300) return false;

    const expected = createHmac("sha256", secret).update(`${t}.${body}`).digest("hex");
    const expBuf = Buffer.from(expected, "hex");
    const sigBuf = Buffer.from(v1, "hex");
    if (expBuf.length !== sigBuf.length) return false;
    return timingSafeEqual(expBuf, sigBuf);
  } catch {
    return false;
  }
}

export async function POST(req: NextRequest) {
  const body   = await req.text();
  const sig    = req.headers.get("stripe-signature") ?? "";
  const secret = process.env.STRIPE_WEBHOOK_SECRET ?? "";

  if (!secret) {
    console.error("STRIPE_WEBHOOK_SECRET not configured");
    return NextResponse.json({ error: "Not configured" }, { status: 500 });
  }

  if (!verifyStripeSignature(body, sig, secret)) {
    console.error("Invalid Stripe webhook signature");
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  const event = JSON.parse(body);
  const obj = event.data.object;

  switch (event.type) {
    case "checkout.session.completed":
      console.log("Checkout completed:", obj.customer_email);
      await notifyTelegram(`🎓 RedSeal Prep: new Pro subscriber — ${obj.customer_details?.email ?? obj.customer_email ?? "unknown"}`);
      break;
    case "customer.subscription.updated":
      console.log(`Subscription ${obj.id} → ${obj.status}`);
      if (obj.cancel_at_period_end) {
        await notifyTelegram(`⚠️ RedSeal Prep: subscription set to cancel at period end (${obj.id})`);
      }
      break;
    case "customer.subscription.deleted":
      console.log("Subscription cancelled:", obj.customer);
      await notifyTelegram(`😢 RedSeal Prep: subscription cancelled (${obj.customer})`);
      break;
    case "invoice.payment_failed":
      console.log("Payment failed:", obj.customer_email);
      await notifyTelegram(`💳 RedSeal Prep: payment FAILED — ${obj.customer_email ?? obj.customer ?? "unknown"}`);
      break;
    default:
      console.log("Unhandled event:", event.type);
  }

  return NextResponse.json({ received: true });
}

// Best-effort ping to Bryan's Telegram; never blocks the 200 back to Stripe
async function notifyTelegram(text: string): Promise<void> {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.TELEGRAM_CHAT_ID;
  if (!token || !chatId) return;
  try {
    await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text }),
    });
  } catch (e) {
    console.error("Telegram notify failed:", e);
  }
}
