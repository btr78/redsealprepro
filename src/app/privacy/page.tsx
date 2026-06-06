export default function Privacy() {
  return (
    <div style={{ fontFamily: "'DM Sans', system-ui, sans-serif", background: "#07090f", minHeight: "100vh", color: "#e6edf3", padding: "60px 20px" }}>
      <div style={{ maxWidth: 720, margin: "0 auto" }}>
        <a href="/" style={{ color: "#8b949e", fontSize: 13, textDecoration: "none" }}>← Back to RedSeal Prep</a>
        <h1 style={{ fontSize: 32, fontWeight: 900, margin: "24px 0 8px" }}>Privacy Policy</h1>
        <p style={{ color: "#8b949e", fontSize: 13, marginBottom: 40 }}>Last updated: June 2026</p>

        {[
          ["Information We Collect", "We collect your email address when you subscribe via Stripe. We do not collect your name, address, or payment card details — these are handled entirely by Stripe and are subject to Stripe's privacy policy. We store no personal data on our own servers beyond what is necessary to verify your subscription status."],
          ["How We Use Your Information", "Your email address is used solely to verify your active subscription. We do not sell, rent, or share your email address with third parties for marketing purposes. We do not send marketing emails."],
          ["Study Data & Local Storage", "Your quiz progress, wrong answers, streak data, and performance statistics are stored locally in your browser's localStorage. This data never leaves your device and is not transmitted to our servers."],
          ["AI Tutor Conversations", "Messages sent to the AI Tutor are processed by Anthropic's Claude API. These messages are subject to Anthropic's privacy policy. We do not store your conversation history on our servers."],
          ["Stripe", "Payment processing is handled by Stripe, Inc. When you subscribe, Stripe stores your payment information. We receive only your email address and subscription status from Stripe. Stripe's privacy policy is available at stripe.com/privacy."],
          ["Cookies", "We do not use cookies for tracking or analytics. Browser localStorage is used only for your study progress as described above."],
          ["Data Retention", "We retain subscription verification data (your email linked to your Stripe customer ID) for the duration of your subscription and a reasonable period thereafter for dispute resolution."],
          ["Your Rights", "You may request deletion of your data by emailing support@redsealprep.pro. To cancel your subscription and associated billing, contact us or manage your subscription through the Stripe customer portal."],
          ["Children's Privacy", "The Service is intended for adults pursuing professional certification. We do not knowingly collect information from individuals under 18 years of age."],
          ["Contact", "For privacy-related inquiries, contact us at support@redsealprep.pro"],
        ].map(([title, body]) => (
          <div key={title} style={{ marginBottom: 28 }}>
            <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 8, color: "#ff6b35" }}>{title}</h2>
            <p style={{ fontSize: 14, color: "#8b949e", lineHeight: 1.7, margin: 0 }}>{body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
