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

  switch (event.type) {
    case "checkout.session.completed":
      console.log("Checkout completed:", event.data.object.customer_email);
      break;
    case "customer.subscription.updated":
      console.log(`Subscription ${event.data.object.id} → ${event.data.object.status}`);
      break;
    case "customer.subscription.deleted":
      console.log("Subscription cancelled:", event.data.object.customer);
      break;
    case "invoice.payment_failed":
      console.log("Payment failed:", event.data.object.customer_email);
      break;
    default:
      console.log("Unhandled event:", event.type);
  }

  return NextResponse.json({ received: true });
}
