import { NextRequest, NextResponse } from "next/server";
import { createHmac, timingSafeEqual } from "crypto";

const MAX_AGE = 30 * 24 * 60 * 60 * 1000;

function isValidToken(token: string): boolean {
  try {
    const secret = process.env.ACTIVATION_SECRET;
    if (!secret) return false;
    const dot = token.lastIndexOf(".");
    if (dot < 0) return false;
    const payload = token.slice(0, dot);
    const sig     = token.slice(dot + 1);
    const expected = createHmac("sha256", secret).update(payload).digest("hex");
    const sigBuf = Buffer.from(sig,      "hex");
    const expBuf = Buffer.from(expected, "hex");
    if (sigBuf.length !== expBuf.length) return false;
    if (!timingSafeEqual(sigBuf, expBuf)) return false;
    const data = JSON.parse(Buffer.from(payload, "base64url").toString());
    return Date.now() - data.iat <= MAX_AGE;
  } catch {
    return false;
  }
}

export async function POST(req: NextRequest) {
  try {
    const { messages, questionContext, token, trade } = await req.json();

    if (!token || !isValidToken(token)) {
      return NextResponse.json(
        { error: "Subscription required", code: "SUBSCRIBE" },
        { status: 401 }
      );
    }

    const tradeName = trade?.name ?? "433A Industrial Mechanic (Millwright)";
    const tradeId   = trade?.id   ?? "433A";

    const systemPrompt =
      `You are an expert Red Seal ${tradeId} ${tradeName} exam tutor. ` +
      `You help tradespeople prepare for the Certificate of Qualification exam. ` +
      `Be concise (2-3 paragraphs max), practical, and reference real-world shop floor scenarios. ` +
      `Use trade terminology naturally. If discussing a specific question, explain WHY each wrong ` +
      `answer is wrong, not just why the right one is right. Include exam tips when relevant.` +
      (questionContext ? `\n\nCurrent question context: ${JSON.stringify(questionContext)}` : "");

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
