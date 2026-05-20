import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

function createToken(email: string, secret: string): string {
  const payload = JSON.stringify({ email, exp: Date.now() + 30 * 24 * 60 * 60 * 1000 });
  const payloadB64 = Buffer.from(payload).toString("base64url");
  const hmac = crypto.createHmac("sha256", secret).update(payloadB64).digest("hex");
  return `${payloadB64}.${hmac}`;
}

function verifyStripeSignature(payload: string, header: string, secret: string): boolean {
  try {
    const parts = header.split(",");
    const t = parts.find(p => p.startsWith("t="))?.slice(2);
    const sig = parts.find(p => p.startsWith("v1="))?.slice(3);
    if (!t || !sig) return false;
    const signed = `${t}.${payload}`;
    const expected = crypto.createHmac("sha256", secret).update(signed, "utf8").digest("hex");
    if (expected.length !== sig.length) return false;
    return crypto.timingSafeEqual(Buffer.from(expected, "hex"), Buffer.from(sig, "hex"));
  } catch {
    return false;
  }
}

async function sendActivationEmail(email: string, token: string, apiKey: string) {
  const link = `https://redsealprep.pro/api/activate?token=${encodeURIComponent(token)}`;
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: "RedSeal Prep <onboarding@resend.dev>",
      to: email,
      subject: "Activate your RedSeal Prep Pro access",
      html: `
        <div style="font-family:sans-serif;max-width:520px;margin:40px auto;padding:32px 24px;background:#07090f;color:#e6edf3;border-radius:12px;border:1px solid #30363d">
          <div style="color:#ff6b35;font-size:28px;margin-bottom:4px">⚙️ RedSeal Prep</div>
          <h1 style="font-size:22px;font-weight:800;margin-bottom:8px">Your Pro access is ready!</h1>
          <p style="color:#8b949e;margin-bottom:28px;font-size:15px">Your 7-day free trial has started. Click below to activate your access on this device.</p>
          <a href="${link}" style="display:inline-block;background:#ff6b35;color:white;text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:700;font-size:16px">Activate Pro Access →</a>
          <p style="color:#8b949e;font-size:12px;margin-top:28px;line-height:1.6">
            This link activates your Pro access on the device you click it from. To activate on another device later, use the <strong style="color:#e6edf3">"Restore Access"</strong> button on redsealprep.pro.<br><br>
            Link expires in 30 days. If you didn't sign up for RedSeal Prep, ignore this email.
          </p>
        </div>
      `,
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    console.error("Resend error:", err);
  }
}

export async function POST(req: NextRequest) {
  const STRIPE_WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET;
  const RESEND_API_KEY = process.env.RESEND_API_KEY;
  const ACTIVATION_SECRET = process.env.ACTIVATION_SECRET;

  try {
    const body = await req.text();

    if (STRIPE_WEBHOOK_SECRET) {
      const sig = req.headers.get("stripe-signature") || "";
      if (!verifyStripeSignature(body, sig, STRIPE_WEBHOOK_SECRET)) {
        console.error("Stripe signature verification failed");
        return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
      }
    }

    const event = JSON.parse(body);

    switch (event.type) {
      case "checkout.session.completed": {
        const session = event.data.object;
        const email = session.customer_email || session.customer_details?.email;
        console.log("New subscription:", email);
        if (email && RESEND_API_KEY && ACTIVATION_SECRET) {
          const token = createToken(email.toLowerCase().trim(), ACTIVATION_SECRET);
          await sendActivationEmail(email, token, RESEND_API_KEY);
          console.log("Activation email sent to:", email);
        }
        break;
      }
      case "customer.subscription.deleted":
        console.log("Subscription cancelled:", event.data.object.customer);
        break;
      case "invoice.payment_failed":
        console.log("Payment failed:", event.data.object.customer_email);
        break;
      default:
        console.log("Unhandled webhook event:", event.type);
    }

    return NextResponse.json({ received: true });
  } catch (error) {
    console.error("Webhook error:", error);
    return NextResponse.json({ error: "Webhook handler failed" }, { status: 400 });
  }
}
