import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const STRIPE_SECRET = process.env.STRIPE_SECRET_KEY;
    const PRICE_ID = process.env.STRIPE_PRICE_ID;

    if (!STRIPE_SECRET || !PRICE_ID) {
      return NextResponse.json({ error: "Stripe not configured" }, { status: 500 });
    }

    const response = await fetch("https://api.stripe.com/v1/checkout/sessions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${STRIPE_SECRET}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({
        "mode": "subscription",
        "payment_method_types[0]": "card",
        "line_items[0][price]": PRICE_ID,
        "line_items[0][quantity]": "1",
        "success_url": "https://redsealprep.pro?sub=success",
        "cancel_url": "https://redsealprep.pro?sub=cancelled",
        "allow_promotion_codes": "true",
        "payment_method_collection": "always",
        "subscription_data[trial_period_days]": "7",
      }),
    });

    const session = await response.json();

    if (session.error) {
      return NextResponse.json({ error: session.error.message }, { status: 400 });
    }

    return NextResponse.json({ url: session.url });
  } catch (error) {
    console.error("Stripe checkout error:", error);
    return NextResponse.json({ error: "Failed to create checkout session" }, { status: 500 });
  }
}
