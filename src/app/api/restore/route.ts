import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

function createToken(email: string, secret: string): string {
  const payload = JSON.stringify({ email, exp: Date.now() + 30 * 24 * 60 * 60 * 1000 });
  const payloadB64 = Buffer.from(payload).toString("base64url");
  const hmac = crypto.createHmac("sha256", secret).update(payloadB64).digest("hex");
  return `${payloadB64}.${hmac}`;
}

async function hasActiveSubscription(email: string, secretKey: string): Promise<boolean> {
  const custRes = await fetch(
    `https://api.stripe.com/v1/customers?email=${encodeURIComponent(email)}&limit=5`,
    { headers: { Authorization: `Bearer ${secretKey}` } }
  );
  const custData = await custRes.json();
  const customers: { id: string }[] = custData.data || [];

  for (const customer of customers) {
    for (const status of ["active", "trialing"]) {
      const subRes = await fetch(
        `https://api.stripe.com/v1/subscriptions?customer=${customer.id}&status=${status}&limit=1`,
        { headers: { Authorization: `Bearer ${secretKey}` } }
      );
      const subData = await subRes.json();
      if (subData.data?.length > 0) return true;
    }
  }
  return false;
}

async function sendRestoreEmail(email: string, token: string, apiKey: string) {
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
      subject: "Your RedSeal Prep Pro access link",
      html: `
        <div style="font-family:sans-serif;max-width:520px;margin:40px auto;padding:32px 24px;background:#07090f;color:#e6edf3;border-radius:12px;border:1px solid #30363d">
          <div style="color:#ff6b35;font-size:28px;margin-bottom:4px">⚙️ RedSeal Prep</div>
          <h1 style="font-size:22px;font-weight:800;margin-bottom:8px">Activate on this device</h1>
          <p style="color:#8b949e;margin-bottom:28px;font-size:15px">Click below to restore your Pro access on this device.</p>
          <a href="${link}" style="display:inline-block;background:#ff6b35;color:white;text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:700;font-size:16px">Activate Pro Access →</a>
          <p style="color:#8b949e;font-size:12px;margin-top:28px;line-height:1.6">
            Link expires in 30 days. You can request a new link anytime from redsealprep.pro.<br><br>
            If you didn't request this, ignore it — nothing will change.
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
  const STRIPE_SECRET_KEY = process.env.STRIPE_SECRET_KEY;
  const RESEND_API_KEY = process.env.RESEND_API_KEY;
  const ACTIVATION_SECRET = process.env.ACTIVATION_SECRET;

  if (!STRIPE_SECRET_KEY || !RESEND_API_KEY || !ACTIVATION_SECRET) {
    return NextResponse.json({ error: "Service not configured" }, { status: 500 });
  }

  try {
    const { email } = await req.json();
    const normalizedEmail = (email || "").toLowerCase().trim();
    if (!normalizedEmail || !normalizedEmail.includes("@")) {
      return NextResponse.json({ error: "Invalid email address" }, { status: 400 });
    }

    const subscribed = await hasActiveSubscription(normalizedEmail, STRIPE_SECRET_KEY);
    if (!subscribed) {
      return NextResponse.json(
        { error: "No active subscription found for this email. Contact btsrana@gmail.com for help." },
        { status: 404 }
      );
    }

    const token = createToken(normalizedEmail, ACTIVATION_SECRET);
    await sendRestoreEmail(email, token, RESEND_API_KEY);

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Restore error:", error);
    return NextResponse.json({ error: "Failed to send access link. Please try again." }, { status: 500 });
  }
}
