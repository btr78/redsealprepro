import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

function verifyToken(token: string, secret: string): { email: string } | null {
  try {
    const dot = token.lastIndexOf(".");
    if (dot === -1) return null;
    const payloadB64 = token.slice(0, dot);
    const hmac = token.slice(dot + 1);
    const expected = crypto.createHmac("sha256", secret).update(payloadB64).digest("hex");
    if (expected.length !== hmac.length) return null;
    if (!crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(hmac))) return null;
    const { email, exp } = JSON.parse(Buffer.from(payloadB64, "base64url").toString());
    if (Date.now() > exp) return null;
    return { email };
  } catch {
    return null;
  }
}

export async function GET(req: NextRequest) {
  const ACTIVATION_SECRET = process.env.ACTIVATION_SECRET;
  if (!ACTIVATION_SECRET) {
    return NextResponse.redirect(new URL("/?sub=error", req.url));
  }

  const token = req.nextUrl.searchParams.get("token") || "";
  const result = verifyToken(token, ACTIVATION_SECRET);

  if (!result) {
    return NextResponse.redirect(new URL("/?sub=invalid", req.url));
  }

  const redirectUrl = new URL("/", req.url);
  redirectUrl.searchParams.set("sub", "success");
  redirectUrl.searchParams.set("email", result.email);
  return NextResponse.redirect(redirectUrl);
}
