import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  // Webhook handler for Stripe subscription events
  // In production, verify the webhook signature using STRIPE_WEBHOOK_SECRET
  try {
    const body = await req.text();
    const event = JSON.parse(body);

    switch (event.type) {
      case "checkout.session.completed":
        // Subscription created — activate user's pro access
        console.log("New subscription:", event.data.object.customer_email);
        break;
      case "customer.subscription.deleted":
        // Subscription cancelled — revoke pro access
        console.log("Subscription cancelled:", event.data.object.customer);
        break;
      case "invoice.payment_failed":
        // Payment failed — notify user
        console.log("Payment failed:", event.data.object.customer_email);
        break;
      default:
        console.log("Unhandled event:", event.type);
    }

    return NextResponse.json({ received: true });
  } catch (error) {
    console.error("Webhook error:", error);
    return NextResponse.json({ error: "Webhook handler failed" }, { status: 400 });
  }
}
