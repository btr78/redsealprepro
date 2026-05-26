import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const { messages, questionContext } = await req.json();

    const systemPrompt = `You are an expert Red Seal 433A Industrial Mechanic (Millwright) exam tutor. You help tradespeople prepare for the Certificate of Qualification exam. Be concise (2-3 paragraphs max), practical, and reference real-world shop floor scenarios. Use trade terminology naturally. If discussing a specific question, explain WHY each wrong answer is wrong, not just why the right one is right. Include exam tips when relevant.${questionContext ? `\n\nCurrent question context: ${JSON.stringify(questionContext)}` : ""}`;

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
