import { NextRequest, NextResponse } from "next/server";

const TRADE_NAMES: Record<string, string> = {
  "433A": "Industrial Mechanic (Millwright)",
  "309A": "Construction Electrician",
  "442A": "Industrial Electrician",
  "306A": "Plumber",
  "430A": "Tool and Die Maker",
  "403A": "Carpenter",
  "310S": "Auto Service Technician",
  "307A": "Steamfitter/Pipefitter",
  "456A": "Welder",
};

export async function POST(req: NextRequest) {
  try {
    const { messages, questionContext, tradeId } = await req.json();

    const tradeCode = tradeId || "433A";
    const tradeName = TRADE_NAMES[tradeCode] || "Industrial Mechanic (Millwright)";

    const systemPrompt = `You are an expert Red Seal ${tradeCode} ${tradeName} exam tutor. You help tradespeople prepare for the Certificate of Qualification exam. Be concise (2-3 paragraphs max), practical, and reference real-world scenarios specific to ${tradeName}. Use trade terminology naturally. If discussing a specific question, explain WHY each wrong answer is wrong, not just why the right one is right. Include exam tips when relevant.${questionContext ? `\n\nCurrent question context: ${JSON.stringify(questionContext)}` : ""}`;

    const resp = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": process.env.ANTHROPIC_API_KEY || "",
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-20250514",
        max_tokens: 1000,
        system: systemPrompt,
        messages: messages.map((m: any) => ({
          role: m.role === "ai" ? "assistant" : m.role,
          content: m.text,
        })),
      }),
    });

    const data = await resp.json();
    const text = data.content?.map((c: any) => c.text || "").join("") || "Sorry, I couldn't process that. Please try again.";

    return NextResponse.json({ text });
  } catch (error) {
    console.error("Chat API error:", error);
    return NextResponse.json({ text: "Connection issue. Please try again." }, { status: 500 });
  }
}
